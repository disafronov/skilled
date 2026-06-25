"""LLM provider client — OpenAI-compatible API."""

import os
from typing import Any

import httpx


def get_global_system_prompt() -> str:
    return os.environ.get("GLOBAL_SYSTEM_PROMPT", "")


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def build_request_body(
    profile: Any,
    skill: Any,
    wrapper: Any,
    raw_input: str,
    global_system_prompt: str,
) -> dict[str, Any]:
    """Build an OpenAI-compatible /chat/completions request body."""

    instructions = "\n\n".join(
        filter(None, [skill.content, wrapper.content, global_system_prompt])
    )

    profile_params = _omit_none(
        {
            "temperature": profile.temperature,
            "top_p": profile.top_p,
            "max_completion_tokens": profile.max_output_tokens,
            "reasoning_effort": profile.reasoning_effort,
        }
    )

    body: dict[str, Any] = {
        "model": profile.model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": raw_input},
        ],
        **profile_params,
    }

    if profile.response_format:
        body["response_format"] = profile.response_format

    return body


def call_llm(
    provider: Any, profile: Any, skill: Any, wrapper: Any, raw_input: str
) -> str:
    """Execute an LLM call and return the response text."""
    instructions = "\n\n".join(
        filter(None, [skill.content, wrapper.content, get_global_system_prompt()])
    )

    provider_params = _omit_none(
        {
            "temperature": profile.temperature,
            "top_p": profile.top_p,
            "max_completion_tokens": profile.max_output_tokens,
            "reasoning_effort": profile.reasoning_effort,
        }
    )

    body: dict[str, Any] = {
        "model": profile.model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": raw_input},
        ],
        **provider_params,
    }

    if profile.response_format:
        body["response_format"] = profile.response_format

    with httpx.Client(base_url=provider.base_url) as client:
        response = client.post(
            "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {provider.auth_token}"},
        )
        response.raise_for_status()
        data = response.json()

    result: str = data["choices"][0]["message"]["content"]
    return result
