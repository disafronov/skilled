"""Tests for sanitization utilities."""

from django.test import SimpleTestCase

from engine.common.sanitize import sanitize_error


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
