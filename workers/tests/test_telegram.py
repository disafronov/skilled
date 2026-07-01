from unittest.mock import patch

import httpx
from django.test import TestCase


class TelegramHttpClientTests(TestCase):
    def _request(self, method: str) -> httpx.Request:
        return httpx.Request(method, "https://example.com")

    @patch("workers.telegram._http.request")
    def test_send_message_posts_payload(self, mock_request):
        from workers.telegram import send_message

        mock_request.return_value = httpx.Response(200, request=self._request("POST"))

        send_message(
            "token",
            "chat",
            "*hello*",
            reply_to_message_id=42,
            parse_mode="MarkdownV2",
        )

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/sendMessage",
            json={
                "chat_id": "chat",
                "text": "*hello*",
                "reply_to_message_id": 42,
                "allow_sending_without_reply": True,
                "parse_mode": "MarkdownV2",
            },
        )

    @patch("workers.telegram._http.request")
    def test_send_message_posts_minimal_payload(self, mock_request):
        from workers.telegram import send_message

        mock_request.return_value = httpx.Response(200, request=self._request("POST"))

        send_message("token", "chat", "hello")

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/sendMessage",
            json={"chat_id": "chat", "text": "hello"},
        )

    @patch("workers.telegram._http.request")
    def test_send_document_posts_file_payload(self, mock_request):
        from workers.telegram import send_document

        mock_request.return_value = httpx.Response(200, request=self._request("POST"))

        send_document(
            "token",
            "chat",
            "content",
            "response.txt",
            "text/plain",
            caption="caption",
            reply_to_message_id=42,
        )

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/sendDocument",
            data={
                "chat_id": "chat",
                "caption": "caption",
                "reply_to_message_id": "42",
                "allow_sending_without_reply": "true",
            },
            files={"document": ("response.txt", b"content", "text/plain")},
        )

    @patch("workers.telegram._http.request")
    def test_send_document_posts_minimal_payload(self, mock_request):
        from workers.telegram import send_document

        mock_request.return_value = httpx.Response(200, request=self._request("POST"))

        send_document("token", "chat", "content", "response.txt", "text/plain")

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/sendDocument",
            data={"chat_id": "chat"},
            files={"document": ("response.txt", b"content", "text/plain")},
        )

    @patch("workers.telegram._http.request")
    def test_send_message_raises_on_api_error(self, mock_request):
        from workers.telegram import send_message

        mock_request.return_value = httpx.Response(
            200,
            request=self._request("POST"),
            json={"ok": False, "description": "Bad Request: can't parse entities"},
        )

        with self.assertRaisesRegex(
            RuntimeError,
            r"Telegram API error: Bad Request: can't parse entities",
        ):
            send_message("token", "chat", "text")

    @patch("workers.telegram._http.request")
    def test_send_message_raises_with_truncated_description(self, mock_request):
        from workers.telegram import send_message

        long_desc = "x" * 200
        mock_request.return_value = httpx.Response(
            200,
            request=self._request("POST"),
            json={"ok": False, "description": long_desc},
        )

        with self.assertRaisesRegex(
            RuntimeError,
            r"Telegram API error: x{117}\.\.\.",
        ):
            send_message("token", "chat", "text")

    @patch("workers.telegram._http.request")
    def test_get_updates_raises_on_api_error(self, mock_request):
        from workers.telegram import get_updates

        mock_request.return_value = httpx.Response(
            200,
            request=self._request("GET"),
            json={"ok": False, "description": "Unauthorized: invalid token"},
        )

        with self.assertRaisesRegex(
            RuntimeError,
            r"Telegram API error: Unauthorized: invalid token",
        ):
            get_updates("bad-token")

    @patch("workers.telegram._http.request")
    def test_get_updates_returns_result(self, mock_request):
        from workers.telegram import get_updates

        mock_request.return_value = httpx.Response(
            200,
            request=self._request("GET"),
            json={"result": [{"update_id": 1}]},
        )

        self.assertEqual(get_updates("token", offset=10), [{"update_id": 1}])
        mock_request.assert_called_once_with(
            "get",
            "https://api.telegram.org/bottoken/getUpdates",
            params={"offset": 10, "timeout": 10},
        )

    @patch("workers.telegram._http.request")
    def test_request_raises_runtime_error_on_connection_error(self, mock_request):
        from workers.telegram import send_message

        mock_request.side_effect = httpx.ConnectError("Connection refused")

        with self.assertRaisesRegex(RuntimeError, "Telegram API request failed"):
            send_message("token", "chat", "hello")

    def test_sanitize_error_strips_token(self):
        from workers.telegram import sanitize_error

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
        from workers.telegram import sanitize_error

        self.assertEqual(sanitize_error("normal error text"), "normal error text")

    def test_http_error_sanitizes_response_body(self):
        from workers.telegram import _raise_for_status

        request = httpx.Request("POST", "https://api.telegram.org/botx/sendMessage")
        response = httpx.Response(
            400,
            request=request,
            text='{"ok":false,"description":"Bad Request: message is too long"}',
        )

        with self.assertRaisesRegex(
            RuntimeError,
            r"Telegram API error \(400\): Bad Request: message is too long",
        ):
            _raise_for_status(response)

    def test_http_error_handles_non_json_body(self):
        from workers.telegram import _raise_for_status

        request = httpx.Request("POST", "https://api.telegram.org/botx/sendMessage")
        response = httpx.Response(
            502,
            request=request,
            text="<html>bad gateway</html>",
        )

        with self.assertRaisesRegex(RuntimeError, r"Telegram API error \(502\)"):
            _raise_for_status(response)

    def test_non_json_response_on_http_200_logs_warning(self):
        from workers.telegram import _raise_for_status

        request = httpx.Request("POST", "https://api.telegram.org/botx/sendMessage")
        response = httpx.Response(
            200,
            request=request,
            text="<html>server error</html>",
        )

        with self.assertLogs("workers.telegram", level="WARNING") as logs:
            _raise_for_status(response)

        self.assertEqual(
            logs.output,
            [
                (
                    "WARNING:workers.telegram:Telegram API returned"
                    " non-JSON response on HTTP 200"
                )
            ],
        )

    def test_http_error_truncates_long_description(self):
        from workers.telegram import _raise_for_status

        request = httpx.Request("POST", "https://api.telegram.org/botx/sendMessage")
        long_desc = "x" * 200
        response = httpx.Response(
            400,
            request=request,
            text=f'{{"ok":false,"description":"{long_desc}"}}',
        )

        with self.assertRaisesRegex(
            RuntimeError, r"Telegram API error \(400\): x{117}\.\.\."
        ):
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

    @patch("workers.telegram._http.request")
    def test_set_webhook_posts_expected_payload(self, mock_request):
        from workers.telegram import set_webhook

        mock_request.return_value = httpx.Response(
            200, request=self._request("POST"), json={"ok": True, "result": {}}
        )

        set_webhook("token", "https://example.com/webhook/token/")

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/setWebhook",
            json={
                "url": "https://example.com/webhook/token/",
                "drop_pending_updates": False,
                "allowed_updates": ["message"],
            },
        )

    @patch("workers.telegram._http.request")
    def test_set_webhook_raises_on_api_error(self, mock_request):
        from workers.telegram import set_webhook

        mock_request.return_value = httpx.Response(
            400,
            request=self._request("POST"),
            json={"ok": False, "description": "Bad webhook"},
        )

        with self.assertRaises(RuntimeError):
            set_webhook("token", "https://example.com/webhook/token/")

    @patch("workers.telegram._http.request")
    def test_set_webhook_with_secret_token(self, mock_request):
        from workers.telegram import set_webhook

        mock_request.return_value = httpx.Response(
            200, request=self._request("POST"), json={"ok": True, "result": {}}
        )

        set_webhook(
            "token",
            "https://example.com/webhook/",
            secret_token="my-secret-value",
        )

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/setWebhook",
            json={
                "url": "https://example.com/webhook/",
                "secret_token": "my-secret-value",
                "drop_pending_updates": False,
                "allowed_updates": ["message"],
            },
        )

    @patch("workers.telegram._http.request")
    def test_delete_webhook_posts_expected_payload(self, mock_request):
        from workers.telegram import delete_webhook

        mock_request.return_value = httpx.Response(
            200, request=self._request("POST"), json={"ok": True, "result": {}}
        )

        delete_webhook("token")

        mock_request.assert_called_once_with(
            "post",
            "https://api.telegram.org/bottoken/deleteWebhook",
            json={"drop_pending_updates": False},
        )

    @patch("workers.telegram._http.request")
    def test_delete_webhook_raises_on_api_error(self, mock_request):
        from workers.telegram import delete_webhook

        mock_request.return_value = httpx.Response(
            400,
            request=self._request("POST"),
            json={"ok": False, "description": "Bad request"},
        )

        with self.assertRaises(RuntimeError):
            delete_webhook("token")

    @patch("workers.telegram._http.request")
    def test_get_webhook_info_returns_result(self, mock_request):
        from workers.telegram import get_webhook_info

        mock_request.return_value = httpx.Response(
            200,
            request=self._request("GET"),
            json={
                "ok": True,
                "result": {
                    "url": "https://example.com/webhook/token/",
                    "pending_update_count": 0,
                },
            },
        )

        result = get_webhook_info("token")

        self.assertEqual(result["url"], "https://example.com/webhook/token/")
        self.assertEqual(result["pending_update_count"], 0)

    @patch("workers.telegram._http.request")
    def test_get_webhook_info_raises_on_api_error(self, mock_request):
        from workers.telegram import get_webhook_info

        mock_request.return_value = httpx.Response(
            400,
            request=self._request("GET"),
            json={"ok": False, "description": "Not found"},
        )

        with self.assertRaises(RuntimeError):
            get_webhook_info("token")
