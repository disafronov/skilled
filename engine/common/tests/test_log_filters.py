"""Tests for BotTokenFilter — logging filter that masks Telegram bot tokens."""

import logging

from django.test import SimpleTestCase

from ..log_filters import BotTokenFilter


class BotTokenFilterTests(SimpleTestCase):
    """Record msg/args with bot token patterns must be masked."""

    def setUp(self):
        self.filter_ = BotTokenFilter()
        self.token = "123456:ABCdefGHIjklmNOPqrstUVwxyz-12345"

    def test_msg_with_token_masked(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"token={self.token}",
            args=None,
            exc_info=None,
        )
        self.filter_.filter(record)
        self.assertNotIn(self.token, record.msg)

    def test_args_with_token_masked(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="token=%s",
            args=(self.token,),
            exc_info=None,
        )
        self.filter_.filter(record)
        self.assertNotIn(self.token, record.args[0])

    def test_non_string_args_unchanged(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="value=%s",
            args=(42,),
            exc_info=None,
        )
        self.filter_.filter(record)
        self.assertEqual(record.args, (42,))

    def test_filter_with_no_args(self):
        """Cover branch: record.args is None — skip tuple comprehension."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="no args",
            args=None,
            exc_info=None,
        )
        self.assertTrue(self.filter_.filter(record))

    def test_filter_with_empty_args(self):
        """Cover branch: record.args is () — falsy, skip comprehension."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="empty args",
            args=(),
            exc_info=None,
        )
        self.assertTrue(self.filter_.filter(record))
