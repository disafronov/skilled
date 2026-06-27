from unittest.mock import patch

import httpx
from django.test import TestCase


class TelegramHttpClientTests(TestCase):
    def _request(self, method: str) -> httpx.Request:
        return httpx.Request(method, "https://example.com")

    @patch("workers.telegram._http.post")
    def test_send_message_posts_payload(self, mock_post):
        from workers.telegram import send_message

        mock_post.return_value = httpx.Response(200, request=self._request("POST"))

        send_message(
            "token",
            "chat",
            "*hello*",
            reply_to_message_id=42,
            parse_mode="MarkdownV2",
        )

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendMessage",
            json={
                "chat_id": "chat",
                "text": "*hello*",
                "reply_to_message_id": 42,
                "allow_sending_without_reply": True,
                "parse_mode": "MarkdownV2",
            },
        )

    @patch("workers.telegram._http.post")
    def test_send_message_posts_minimal_payload(self, mock_post):
        from workers.telegram import send_message

        mock_post.return_value = httpx.Response(200, request=self._request("POST"))

        send_message("token", "chat", "hello")

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendMessage",
            json={"chat_id": "chat", "text": "hello"},
        )

    @patch("workers.telegram._http.post")
    def test_send_document_posts_file_payload(self, mock_post):
        from workers.telegram import send_document

        mock_post.return_value = httpx.Response(200, request=self._request("POST"))

        send_document(
            "token",
            "chat",
            "content",
            "response.txt",
            "text/plain",
            caption="caption",
            reply_to_message_id=42,
        )

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendDocument",
            data={
                "chat_id": "chat",
                "caption": "caption",
                "reply_to_message_id": "42",
                "allow_sending_without_reply": "true",
            },
            files={"document": ("response.txt", b"content", "text/plain")},
        )

    @patch("workers.telegram._http.post")
    def test_send_document_posts_minimal_payload(self, mock_post):
        from workers.telegram import send_document

        mock_post.return_value = httpx.Response(200, request=self._request("POST"))

        send_document("token", "chat", "content", "response.txt", "text/plain")

        mock_post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendDocument",
            data={"chat_id": "chat"},
            files={"document": ("response.txt", b"content", "text/plain")},
        )

    @patch("workers.telegram._http.get")
    def test_get_updates_returns_result(self, mock_get):
        from workers.telegram import get_updates

        mock_get.return_value = httpx.Response(
            200,
            request=self._request("GET"),
            json={"result": [{"update_id": 1}]},
        )

        self.assertEqual(get_updates("token", offset=10), [{"update_id": 1}])
        mock_get.assert_called_once_with(
            "https://api.telegram.org/bottoken/getUpdates",
            params={"offset": 10, "timeout": 10},
        )

    def test_http_error_includes_response_body(self):
        from workers.telegram import _raise_for_status

        request = httpx.Request("POST", "https://api.telegram.org/botx/sendMessage")
        response = httpx.Response(
            400,
            request=request,
            text='{"ok":false,"description":"Bad Request: message is too long"}',
        )

        with self.assertRaisesRegex(RuntimeError, "message is too long"):
            _raise_for_status(response)

    def test_detects_document_formats(self):
        from workers.telegram import (
            TELEGRAM_DOCUMENT_FORMAT_HTML,
            TELEGRAM_DOCUMENT_FORMAT_MARKDOWN,
            TELEGRAM_DOCUMENT_FORMAT_TEXT,
            detect_document_format,
        )

        self.assertEqual(
            detect_document_format("<b>Hello</b>"),
            TELEGRAM_DOCUMENT_FORMAT_HTML,
        )
        self.assertEqual(
            detect_document_format("<div>Hello</div>"),
            TELEGRAM_DOCUMENT_FORMAT_HTML,
        )
        self.assertEqual(
            detect_document_format("**Hello**"),
            TELEGRAM_DOCUMENT_FORMAT_MARKDOWN,
        )
        self.assertEqual(
            detect_document_format("Hello"),
            TELEGRAM_DOCUMENT_FORMAT_TEXT,
        )

    def test_document_format_metadata(self):
        from workers.telegram import (
            TELEGRAM_DOCUMENT_FORMAT_HTML,
            TELEGRAM_DOCUMENT_FORMAT_MARKDOWN,
            TELEGRAM_DOCUMENT_FORMAT_TEXT,
            document_format_content_type,
            document_format_filename,
        )

        self.assertEqual(
            document_format_filename(123, TELEGRAM_DOCUMENT_FORMAT_HTML),
            "response-123.html",
        )
        self.assertEqual(
            document_format_filename(123, TELEGRAM_DOCUMENT_FORMAT_MARKDOWN),
            "response-123.md",
        )
        self.assertEqual(
            document_format_filename(123, TELEGRAM_DOCUMENT_FORMAT_TEXT),
            "response-123.txt",
        )
        self.assertEqual(
            document_format_content_type(TELEGRAM_DOCUMENT_FORMAT_HTML),
            "text/html",
        )
        self.assertEqual(
            document_format_content_type(TELEGRAM_DOCUMENT_FORMAT_MARKDOWN),
            "text/markdown",
        )
        self.assertEqual(
            document_format_content_type(TELEGRAM_DOCUMENT_FORMAT_TEXT),
            "text/plain",
        )
