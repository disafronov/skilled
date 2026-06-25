import requests


def send_message(token: str, chat_id: str, text: str) -> dict:
    """Send a message via Telegram Bot API and return the response JSON."""
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    response = requests.post(url, json={
        'chat_id': chat_id,
        'text': text,
    }, timeout=30)
    response.raise_for_status()
    return response.json()


def get_updates(token: str, offset: int | None = None) -> dict:
    """Poll updates from Telegram Bot API."""
    url = f'https://api.telegram.org/bot{token}/getUpdates'
    params: dict = {'timeout': 10}
    if offset is not None:
        params['offset'] = offset
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()
