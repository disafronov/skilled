"""Telegram Bot API client wrapper."""

from typing import Any

import httpx

TELEGRAM_MESSAGE_CHAR_LIMIT = 4096


def send_message(
    token: str,
    chat_id: int | str,
    text: str,
    reply_to_message_id: int | None = None,
) -> None:
    """Send a text message via Telegram Bot API."""
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
        payload["allow_sending_without_reply"] = True

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
        )
        response.raise_for_status()


def send_document(
    token: str,
    chat_id: int | str,
    content: str,
    filename: str,
    caption: str | None = None,
    reply_to_message_id: int | None = None,
) -> None:
    """Send text content as a document via Telegram Bot API."""
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = str(reply_to_message_id)
        data["allow_sending_without_reply"] = "true"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=data,
            files={
                "document": (
                    filename,
                    content.encode("utf-8"),
                    "text/markdown",
                )
            },
        )
        response.raise_for_status()


def get_updates(token: str, offset: int | None = None) -> list[dict[str, object]]:
    """Fetch incoming updates via long-poll."""
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 10},
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data.get("result", [])  # type: ignore[no-any-return]
