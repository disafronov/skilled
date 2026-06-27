"""Telegram Bot API client wrapper."""

import html
import html.parser
import re
from typing import Any
from urllib.parse import urlparse

import httpx

TELEGRAM_MESSAGE_CHAR_LIMIT = 4096
TELEGRAM_PARSE_MODE_HTML = "HTML"
TELEGRAM_PARSE_MODE_MARKDOWN_V2 = "MarkdownV2"
TELEGRAM_DOCUMENT_FORMAT_HTML = "html"
TELEGRAM_DOCUMENT_FORMAT_MARKDOWN = "markdown"
TELEGRAM_DOCUMENT_FORMAT_TEXT = "text"

_TELEGRAM_HTML_TAG_RE = re.compile(
    r"</?(?:b|strong|i|em|u|ins|s|strike|del|tg-spoiler|a|code|pre|blockquote)"
    r"(?:\s+[^>]*)?>",
    re.IGNORECASE,
)
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
_TELEGRAM_MARKDOWN_V2_PATTERNS = (
    re.compile(r"```[\s\S]+?```"),
    re.compile(r"`[^`\n]+`"),
    re.compile(r"(?<!\*)\*[^*\n]+\*(?!\*)"),
    re.compile(r"(?<!_)_[^_\n]+_(?!_)"),
    re.compile(r"__[^_\n]+__"),
    re.compile(r"~[^~\n]+~"),
    re.compile(r"\|\|[^|\n]+\|\|"),
    re.compile(r"\[[^\]\n]+\]\([^) \n]+\)"),
)
_MARKDOWN_V2_SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!"
_MARKDOWN_V2_TOKEN_RE = re.compile(
    r"```(?P<fence>[\s\S]*?)```"
    r"|`(?P<code>[^`\n]+)`"
    r"|\[(?P<link_label>[^\]\n]+)\]\((?P<link_url>[^)\n]+)\)"
    r"|\|\|(?P<spoiler>[^|\n]+)\|\|"
    r"|__(?P<underline>[^_\n]+)__"
    r"|(?<!\*)\*(?P<bold>[^*\n]+)\*(?!\*)"
    r"|(?<!_)_(?P<italic>[^_\n]+)_(?!_)"
    r"|~(?P<strike>[^~\n]+)~"
)
_TEXT_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ALLOWED_HTML_TAGS = {
    "a",
    "b",
    "blockquote",
    "code",
    "del",
    "em",
    "i",
    "ins",
    "pre",
    "s",
    "strike",
    "strong",
    "tg-spoiler",
    "u",
}
_SAFE_LINK_SCHEMES = {"http", "https", "mailto", "tg"}


class _HtmlTagDetector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_tag = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.has_tag = True

    def handle_endtag(self, tag: str) -> None:
        self.has_tag = True


class _TelegramHtmlSanitizer(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in _ALLOWED_HTML_TAGS:
            return

        attr_text = "".join(
            f' {name}="{html.escape(value, quote=True)}"'
            for name, value in self._sanitize_attrs(tag, attrs)
        )
        self.parts.append(f"<{tag}{attr_text}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _ALLOWED_HTML_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def get_html(self) -> str:
        return "".join(self.parts)

    def _sanitize_attrs(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> list[tuple[str, str]]:
        sanitized = []
        for name, value in attrs:
            if value is None:
                continue
            name = name.lower()
            if tag == "a" and name == "href" and _is_safe_link(value):
                sanitized.append((name, value))
            elif tag == "code" and name == "class" and value.startswith("language-"):
                sanitized.append((name, value))
        return sanitized


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(exc.response.text) from None


def _is_safe_link(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme.lower() in _SAFE_LINK_SCHEMES


def _escape_markdown_v2_text(text: str) -> str:
    return re.sub(
        f"([{re.escape(_MARKDOWN_V2_SPECIAL_CHARS)}])",
        r"\\\1",
        text,
    )


def _escape_markdown_v2_code(text: str) -> str:
    return re.sub(r"([`\\])", r"\\\1", text)


def _escape_markdown_v2_link_url(text: str) -> str:
    return re.sub(r"([)\\])", r"\\\1", text)


def _has_parseable_html_tag(text: str, tag_re: re.Pattern[str]) -> bool:
    if not tag_re.search(text):
        return False

    parser = _HtmlTagDetector()
    parser.feed(text)
    return parser.has_tag


def _looks_like_telegram_html(text: str) -> bool:
    return _has_parseable_html_tag(text, _TELEGRAM_HTML_TAG_RE)


def _looks_like_standard_html(text: str) -> bool:
    return _has_parseable_html_tag(text, _STANDARD_HTML_TAG_RE)


def _looks_like_standard_markdown(text: str) -> bool:
    return any(pattern.search(text) for pattern in _STANDARD_MARKDOWN_PATTERNS)


def _looks_like_telegram_markdown_v2(text: str) -> bool:
    return any(pattern.search(text) for pattern in _TELEGRAM_MARKDOWN_V2_PATTERNS)


def detect_parse_mode(text: str) -> str | None:
    """Detect Telegram parse mode for short text responses."""
    if _looks_like_telegram_html(text):
        return TELEGRAM_PARSE_MODE_HTML
    if _looks_like_telegram_markdown_v2(text):
        return TELEGRAM_PARSE_MODE_MARKDOWN_V2
    return None


def prepare_message_text(text: str, parse_mode: str | None) -> str:
    """Prepare text for the selected Telegram parse mode."""
    if parse_mode == TELEGRAM_PARSE_MODE_HTML:
        sanitizer = _TelegramHtmlSanitizer()
        sanitizer.feed(text)
        return sanitizer.get_html()
    if parse_mode == TELEGRAM_PARSE_MODE_MARKDOWN_V2:
        return sanitize_markdown_v2(text)
    return _TEXT_CONTROL_CHARS_RE.sub("", text)


def sanitize_markdown_v2(text: str) -> str:
    parts = []
    last_end = 0
    # fmt: off
    for match in _MARKDOWN_V2_TOKEN_RE.finditer(text):
        parts.append(_escape_markdown_v2_text(text[last_end:match.start()]))
        parts.append(_sanitize_markdown_v2_token(match))
        last_end = match.end()
    # fmt: on
    parts.append(_escape_markdown_v2_text(text[last_end:]))
    return "".join(parts)


def _sanitize_markdown_v2_token(match: re.Match[str]) -> str:
    groups = match.groupdict()
    if groups["fence"] is not None:
        return f"```{_escape_markdown_v2_code(groups['fence'])}```"
    if groups["code"] is not None:
        return f"`{_escape_markdown_v2_code(groups['code'])}`"
    if groups["link_label"] is not None and groups["link_url"] is not None:
        label = _escape_markdown_v2_text(groups["link_label"])
        url = _escape_markdown_v2_link_url(groups["link_url"])
        return f"[{label}]({url})"
    if groups["spoiler"] is not None:
        return f"||{_escape_markdown_v2_text(groups['spoiler'])}||"
    if groups["underline"] is not None:
        return f"__{_escape_markdown_v2_text(groups['underline'])}__"
    if groups["bold"] is not None:
        return f"*{_escape_markdown_v2_text(groups['bold'])}*"
    if groups["italic"] is not None:
        return f"_{_escape_markdown_v2_text(groups['italic'])}_"
    if groups["strike"] is not None:
        return f"~{_escape_markdown_v2_text(groups['strike'])}~"
    return _escape_markdown_v2_text(match.group(0))


def detect_document_format(text: str) -> str:
    """Detect the best file format for long text responses."""
    if _looks_like_standard_html(text):
        return TELEGRAM_DOCUMENT_FORMAT_HTML
    if _looks_like_standard_markdown(text):
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
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
        payload["allow_sending_without_reply"] = True
    if parse_mode:
        payload["parse_mode"] = parse_mode

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
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
                    content_type,
                )
            },
        )
        _raise_for_status(response)


def get_updates(token: str, offset: int | None = None) -> list[dict[str, object]]:
    """Fetch incoming updates via long-poll."""
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 10},
        )
        _raise_for_status(response)
        data: dict[str, Any] = response.json()
        return data.get("result", [])  # type: ignore[no-any-return]
