"""Telegram Bot API client wrapper."""

import atexit
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BOT_API_BASE = "https://api.telegram.org/bot"

_BOT_TOKEN_RE = re.compile(r"\d+:[A-Za-z0-9_-]{20,}")

TELEGRAM_MESSAGE_CHAR_LIMIT = 4096
TELEGRAM_DOCUMENT_FORMAT_HTML = "html"
TELEGRAM_DOCUMENT_FORMAT_MARKDOWN = "markdown"
TELEGRAM_DOCUMENT_FORMAT_TEXT = "text"


def _bot_url(token: str, method: str) -> str:
    return f"{_BOT_API_BASE}{token}/{method}"


_STANDARD_HTML_TAG_RE = re.compile(r"</?[a-z][a-z0-9-]*(?:\s+[^>]*)?>", re.IGNORECASE)
_STANDARD_MARKDOWN_PATTERNS = (
    re.compile(r"```[\s\S]+?```"),
    re.compile(r"`[^`\n]+`"),
    re.compile(r"\*\*[^*\n]+\*\*"),
    re.compile(r"(?<!\*)\*[^*\n]+\*(?!\*)"),
    re.compile(r"__[^_\n]+__"),
    re.compile(r"(?<!_)_[^_\n]+_(?!_)"),
    re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE),
    re.compile(r"^\s{0,3}[-*+]\s+\S", re.MULTILINE),
    re.compile(r"^\s{0,3}\d+\.\s+\S", re.MULTILINE),
    re.compile(r"\[[^\]\n]+\]\([^) \n]+\)"),
)

_http = httpx.Client(timeout=60.0)
atexit.register(_http.close)


def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    logger.debug("Telegram API request: %s", method)
    try:
        response = _http.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        logger.error("Telegram API request failed: %s", method)
        raise RuntimeError("Telegram API request failed") from exc
    return response


def sanitize_error(text: str) -> str:
    return _BOT_TOKEN_RE.sub("***", text)


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            body = exc.response.json()
            description = body.get("description", "")
            if len(description) > 120:
                description = description[:117] + "..."
            msg = f"Telegram API error ({exc.response.status_code}): {description}"
        except Exception:
            msg = f"Telegram API error ({exc.response.status_code})"
        raise RuntimeError(msg) from None

    try:
        body = response.json()
        if not body.get("ok", True):
            description = body.get("description", "")
            if len(description) > 120:
                description = description[:117] + "..."
            raise RuntimeError(f"Telegram API error: {description}")
    except RuntimeError:
        raise
    except Exception:
        logger.warning("Telegram API returned non-JSON response on HTTP 200")


def detect_document_format(text: str) -> str:
    """Detect the best file format for long text responses."""
    if _STANDARD_HTML_TAG_RE.search(text):
        return TELEGRAM_DOCUMENT_FORMAT_HTML
    if any(pattern.search(text) for pattern in _STANDARD_MARKDOWN_PATTERNS):
        return TELEGRAM_DOCUMENT_FORMAT_MARKDOWN
    return TELEGRAM_DOCUMENT_FORMAT_TEXT


def document_format_filename(job_id: int | None, document_format: str) -> str:
    extension = {
        TELEGRAM_DOCUMENT_FORMAT_HTML: "html",
        TELEGRAM_DOCUMENT_FORMAT_MARKDOWN: "md",
        TELEGRAM_DOCUMENT_FORMAT_TEXT: "txt",
    }[document_format]
    return f"response-{job_id}.{extension}"


def document_format_content_type(document_format: str) -> str:
    return {
        TELEGRAM_DOCUMENT_FORMAT_HTML: "text/html",
        TELEGRAM_DOCUMENT_FORMAT_MARKDOWN: "text/markdown",
        TELEGRAM_DOCUMENT_FORMAT_TEXT: "text/plain",
    }[document_format]


def send_message(
    token: str,
    chat_id: int | str,
    text: str,
    reply_to_message_id: int | None = None,
    parse_mode: str | None = None,
) -> None:
    """Send a text message via Telegram Bot API."""
    logger.info("Sending message to chat %s (%d chars)", chat_id, len(text))
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
        payload["allow_sending_without_reply"] = True
    if parse_mode:
        payload["parse_mode"] = parse_mode

    response = _request(
        "post",
        _bot_url(token, "sendMessage"),
        json=payload,
    )
    _raise_for_status(response)


def send_document(
    token: str,
    chat_id: int | str,
    content: str,
    filename: str,
    content_type: str,
    caption: str | None = None,
    reply_to_message_id: int | None = None,
) -> None:
    """Send text content as a document via Telegram Bot API."""
    logger.info(
        "Sending document to chat %s: %s (%d chars)",
        chat_id,
        filename,
        len(content),
    )
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = str(reply_to_message_id)
        data["allow_sending_without_reply"] = "true"

    response = _request(
        "post",
        _bot_url(token, "sendDocument"),
        data=data,
        files={
            "document": (
                filename,
                content.encode("utf-8"),
                content_type,
            )
        },
    )
    _raise_for_status(response)


def get_updates(token: str, offset: int | None = None) -> list[dict[str, Any]]:
    """Fetch incoming updates via long-poll."""
    logger.debug("Fetching Telegram updates (offset=%s)", offset)
    response = _request(
        "get",
        _bot_url(token, "getUpdates"),
        params={"offset": offset, "timeout": 10},
    )
    _raise_for_status(response)
    data: dict[str, Any] = response.json()
    results: list[dict[str, Any]] = data.get("result", [])
    logger.info("Fetched %d Telegram updates (offset=%s)", len(results), offset)
    return results


def set_webhook(token: str, url: str) -> dict[str, Any]:
    """Register a webhook URL for the bot.

    Args:
        token: Bot API token.
        url: Full HTTPS URL (including ``/webhook/<token>/``).

    Returns:
        The response ``result`` dict from Telegram API.
    """
    logger.info("Registering webhook for bot")
    response = _request(
        "post",
        _bot_url(token, "setWebhook"),
        json={
            "url": url,
            "drop_pending_updates": False,
            "allowed_updates": ["message"],
        },
    )
    _raise_for_status(response)
    data: dict[str, Any] = response.json()
    result: dict[str, Any] = data.get("result", {})
    return result


def delete_webhook(token: str) -> dict[str, Any]:
    """Remove the registered webhook and fall back to polling.

    Args:
        token: Bot API token.

    Returns:
        The response ``result`` dict from Telegram API.
    """
    logger.info("Removing webhook for bot")
    response = _request(
        "post",
        _bot_url(token, "deleteWebhook"),
        json={"drop_pending_updates": True},
    )
    _raise_for_status(response)
    data: dict[str, Any] = response.json()
    result: dict[str, Any] = data.get("result", {})
    return result


def get_webhook_info(token: str) -> dict[str, Any]:
    """Retrieve current webhook registration status.

    Returns:
        The response ``result`` dict (keys: url, has_custom_certificate,
        pending_update_count, last_error_date, last_error_message,
        max_connections, allowed_updates).
    """
    logger.debug("Fetching webhook info for bot")
    response = _request("get", _bot_url(token, "getWebhookInfo"))
    _raise_for_status(response)
    data: dict[str, Any] = response.json()
    result: dict[str, Any] = data.get("result", {})
    return result
