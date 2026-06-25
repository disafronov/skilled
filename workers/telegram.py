"""Telegram Bot API client wrapper."""

from typing import Any

import httpx


def send_message(token: str, chat_id: int | str, text: str) -> None:
    """Send a text message via Telegram Bot API."""
    with httpx.Client() as client:
        client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )


def get_updates(token: str, offset: int | None = None) -> list[dict[str, object]]:
    """Fetch incoming updates via long-poll."""
    with httpx.Client() as client:
        response = client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 10},
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data.get("result", [])  # type: ignore[no-any-return]
