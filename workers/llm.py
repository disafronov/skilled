"""LLM provider client — OpenAI-compatible API."""

import os
from typing import Any

from openai import OpenAI


def get_global_system_prompt() -> str:
    return os.environ.get("GLOBAL_SYSTEM_PROMPT", "")


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _build_kwargs(profile) -> dict[str, Any]:
    """Build optional kwargs from profile, omitting null fields."""
    return _omit_none({
        "temperature": profile.temperature,
        "top_p": profile.top_p,
        "max_completion_tokens": profile.max_output_tokens,
        "reasoning_effort": profile.reasoning_effort,
    })


def build_request_body(
    profile,
    skill,
    wrapper,
    raw_input: str,
    global_system_prompt: str,
) -> dict[str, Any]:
    """Build an OpenAI-compatible /chat/completions request body."""

    instructions = "\n\n".join(filter(None, [skill.content, wrapper.content, global_system_prompt]))

    body: dict[str, Any] = {
        "model": profile.model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": raw_input},
        ],
        **_build_kwargs(profile),
    }

    if profile.response_format:
        body["response_format"] = profile.response_format

    return body


def call_llm(provider, profile, skill, wrapper, raw_input: str) -> str:
    """Execute an LLM call and return the response text."""
    body = build_request_body(profile, skill, wrapper, raw_input, get_global_system_prompt())

    client = OpenAI(
        base_url=provider.base_url,
        api_key=provider.auth_token,
    )

    response = client.chat.completions.create(**body)
    return response.choices[0].message.content
