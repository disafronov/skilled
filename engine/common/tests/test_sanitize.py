"""Tests for sanitization utilities and bot token log filtering."""

import logging

from django.test import SimpleTestCase

from ..sanitize import BotTokenFilter, sanitize_error


class SanitizeErrorTests(SimpleTestCase):
    def test_sanitize_error_strips_token(self):
        url = (
            "https://api.telegram.org/"
            "bot7347420035:AAFJ20UAtLRp2Dzq_63bsj5a4wxlWJleh_4/"
            "sendMessage"
        )
        original = f"Client error '400 Bad Request' for url '{url}'"
        sanitized = sanitize_error(original)
        self.assertNotIn(
            "7347420035:AAFJ20UAtLRp2Dzq_63bsj5a4wxlWJleh_4",
            sanitized,
        )
        self.assertIn("sendMessage", sanitized)

    def test_sanitize_error_leaves_clean_text(self):
        self.assertEqual(sanitize_error("normal error text"), "normal error text")


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
