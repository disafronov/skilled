import os

import requests


def get_global_system_prompt() -> str:
    return os.getenv('GLOBAL_SYSTEM_PROMPT', '')


def build_request_body(profile, skill, wrapper, raw_input: str, global_system_prompt: str) -> dict:
    """Build the OpenAI-compatible request body from domain entities."""
    instructions_parts = [skill.content, wrapper.content]
    if global_system_prompt:
        instructions_parts.append(global_system_prompt)
    instructions = '\n\n'.join(instructions_parts)

    messages = [
        {'role': 'system', 'content': instructions},
        {'role': 'user', 'content': raw_input},
    ]

    body: dict = {
        'model': profile.model,
        'messages': messages,
    }

    if profile.temperature is not None:
        body['temperature'] = profile.temperature
    if profile.top_p is not None:
        body['top_p'] = profile.top_p
    if profile.max_output_tokens is not None:
        body['max_tokens'] = profile.max_output_tokens
    if profile.reasoning_effort is not None:
        body['reasoning_effort'] = profile.reasoning_effort
    if profile.response_format is not None:
        body['response_format'] = profile.response_format

    return body


def call_llm(provider, profile, skill, wrapper, raw_input: str) -> str:
    """Call an OpenAI-compatible API and return the response text."""
    global_system_prompt = get_global_system_prompt()
    body = build_request_body(profile, skill, wrapper, raw_input, global_system_prompt)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {provider.auth_token}',
    }

    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    response = requests.post(url, headers=headers, json=body, timeout=120)
    response.raise_for_status()
    data = response.json()

    return data['choices'][0]['message']['content']
