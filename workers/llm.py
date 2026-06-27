"""LLM provider client — OpenAI-compatible API."""

import os
from pathlib import Path
from typing import Any

from django.conf import settings
from openai import OpenAI


def get_global_system_prompt() -> str:
    path = Path(
        os.environ.get(
            "POLICY_FILE",
            settings.BASE_DIR / "policy.md",
        )
    )
    if not path.is_absolute():
        path = settings.BASE_DIR / path

    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _build_kwargs(profile: Any) -> dict[str, Any]:
    """Build optional kwargs from profile, omitting null fields."""
    return _omit_none(
        {
            "temperature": profile.temperature,
            "top_p": profile.top_p,
            "max_completion_tokens": profile.max_output_tokens,
            "reasoning_effort": profile.reasoning_effort,
        }
    )


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


def call_llm(
    provider: Any,
    profile: Any,
    skill: Any,
    wrapper: Any,
    raw_input: str,
) -> str:
    """Execute an LLM call and return the response text."""
    body = build_request_body(
        profile, skill, wrapper, raw_input, get_global_system_prompt()
    )

    client = OpenAI(
        base_url=provider.base_url,
        api_key=provider.auth_token,
    )

    response = client.chat.completions.create(**body)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str):
        raise RuntimeError(
            f"LLM returned empty response (finish_reason: {choice.finish_reason})"
        )
    return content
