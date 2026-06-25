from unittest.mock import MagicMock, patch

import httpx
from django.test import TestCase

from workers.telegram import (
    TELEGRAM_PARSE_MODE_HTML,
    TELEGRAM_PARSE_MODE_MARKDOWN_V2,
    _sanitize_markdown_v2_token,
    prepare_message_text,
    sanitize_markdown_v2,
)


class TelegramHttpClientTests(TestCase):
    def _client_cm(self, response: httpx.Response) -> MagicMock:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = None
        client.post.return_value = response
        client.get.return_value = response
        return client

    @patch("workers.telegram.httpx.Client")
    def test_send_message_posts_payload(self, client_cls):
        from workers.telegram import send_message

        request = httpx.Request("POST", "https://example.com")
        client = self._client_cm(httpx.Response(200, request=request))
        client_cls.return_value = client

        send_message(
            "token",
            "chat",
            "*hello*",
            reply_to_message_id=42,
            parse_mode=TELEGRAM_PARSE_MODE_MARKDOWN_V2,
        )

        client.post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendMessage",
            json={
                "chat_id": "chat",
                "text": "*hello*",
                "reply_to_message_id": 42,
                "allow_sending_without_reply": True,
                "parse_mode": TELEGRAM_PARSE_MODE_MARKDOWN_V2,
            },
        )

    @patch("workers.telegram.httpx.Client")
    def test_send_message_posts_minimal_payload(self, client_cls):
        from workers.telegram import send_message

        request = httpx.Request("POST", "https://example.com")
        client = self._client_cm(httpx.Response(200, request=request))
        client_cls.return_value = client

        send_message("token", "chat", "hello")

        client.post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendMessage",
            json={"chat_id": "chat", "text": "hello"},
        )

    @patch("workers.telegram.httpx.Client")
    def test_send_document_posts_file_payload(self, client_cls):
        from workers.telegram import send_document

        request = httpx.Request("POST", "https://example.com")
        client = self._client_cm(httpx.Response(200, request=request))
        client_cls.return_value = client

        send_document(
            "token",
            "chat",
            "content",
            "response.txt",
            "text/plain",
            caption="caption",
            reply_to_message_id=42,
        )

        client.post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendDocument",
            data={
                "chat_id": "chat",
                "caption": "caption",
                "reply_to_message_id": "42",
                "allow_sending_without_reply": "true",
            },
            files={"document": ("response.txt", b"content", "text/plain")},
        )

    @patch("workers.telegram.httpx.Client")
    def test_send_document_posts_minimal_payload(self, client_cls):
        from workers.telegram import send_document

        request = httpx.Request("POST", "https://example.com")
        client = self._client_cm(httpx.Response(200, request=request))
        client_cls.return_value = client

        send_document("token", "chat", "content", "response.txt", "text/plain")

        client.post.assert_called_once_with(
            "https://api.telegram.org/bottoken/sendDocument",
            data={"chat_id": "chat"},
            files={"document": ("response.txt", b"content", "text/plain")},
        )

    @patch("workers.telegram.httpx.Client")
    def test_get_updates_returns_result(self, client_cls):
        from workers.telegram import get_updates

        request = httpx.Request("GET", "https://example.com")
        client = self._client_cm(
            httpx.Response(200, request=request, json={"result": [{"update_id": 1}]})
        )
        client_cls.return_value = client

        self.assertEqual(get_updates("token", offset=10), [{"update_id": 1}])
        client.get.assert_called_once_with(
            "https://api.telegram.org/bottoken/getUpdates",
            params={"offset": 10, "timeout": 10},
        )

    def test_html_sanitizer_preserves_entities_charrefs_and_code_language(self):
        self.assertEqual(
            prepare_message_text(
                '<code class="language-python" bad>print(&amp; &#35;)</code>',
                TELEGRAM_PARSE_MODE_HTML,
            ),
            '<code class="language-python">print(&amp; &#35;)</code>',
        )

    def test_markdown_v2_sanitizes_all_supported_tokens(self):
        self.assertEqual(
            sanitize_markdown_v2(
                "```a`b\\c``` `a` [a_b](https://x.test/a)b) "
                "||s!|| __u!__ *b!*. _i!_ ~x!~"
            ),
            r"```a\`b\\c``` `a` [a\_b](https://x.test/a)b\) "
            r"||s\!|| __u\!__ *b\!*\. _i\!_ ~x\!~",
        )

    def test_markdown_v2_token_fallback_escapes_raw_match(self):
        match = MagicMock()
        match.groupdict.return_value = {
            "fence": None,
            "code": None,
            "link_label": None,
            "link_url": None,
            "spoiler": None,
            "underline": None,
            "bold": None,
            "italic": None,
            "strike": None,
        }
        match.group.return_value = "raw!"

        self.assertEqual(_sanitize_markdown_v2_token(match), r"raw\!")
