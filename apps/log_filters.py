"""Logging filter that masks Telegram bot tokens in log records."""

import logging
import re

_BOT_TOKEN_RE = re.compile(r"\d+:[A-Za-z0-9_-]{20,}")


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
