"""Sanitization utilities for safe error messages and logging."""

import logging
import re

_BOT_TOKEN_RE = re.compile(r"\d+:[A-Za-z0-9_-]{20,}")


def sanitize_error(text: str) -> str:
    return _BOT_TOKEN_RE.sub("***", text)


class BotTokenFilter(logging.Filter):
    """Replace bot token patterns (digits:35chars) with *** in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _BOT_TOKEN_RE.sub("***", record.msg)
        if record.args:
            record.args = tuple(
                _BOT_TOKEN_RE.sub("***", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True
