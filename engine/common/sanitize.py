"""Sanitization utilities for safe error messages and logging."""

import re

_BOT_TOKEN_RE = re.compile(r"\d+:[A-Za-z0-9_-]{20,}")


def sanitize_error(text: str) -> str:
    return _BOT_TOKEN_RE.sub("***", text)
