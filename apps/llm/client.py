"""LLM provider client — OpenAI-compatible API."""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class _ProviderProto(Protocol):
    """Minimal provider contract: URL + auth token."""

    base_url: str
    auth_token: str


class _ProfileProto(Protocol):
    """Minimal profile contract: model name + optional parameters."""

    model: str
    temperature: float | None
    top_p: float | None
    max_output_tokens: int | None
    reasoning_effort: str | None
    response_format: Any | None


class _SkillProto(Protocol):
    """Minimal skill contract: system-instruction content."""

    content: str


class _WrapperProto(Protocol):
    """Minimal wrapper contract: wrapper-instruction content."""

    content: str


@lru_cache(maxsize=16)
def _get_openai_client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key)


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
        logger.warning(
            "policy file not found at %s — continuing without global policy", path
        )
        return ""
    except (OSError, UnicodeDecodeError) as exc:
        logger.error(
            "Failed to read policy file at %s — %s",
            path,
            exc,
        )
        return ""


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _build_kwargs(profile: _ProfileProto) -> dict[str, Any]:
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
    profile: _ProfileProto,
    skill: _SkillProto,
    wrapper: _WrapperProto,
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
    provider: _ProviderProto,
    profile: _ProfileProto,
    skill: _SkillProto,
    wrapper: _WrapperProto,
    raw_input: str,
) -> str:
    """Execute an LLM call and return the response text."""
    logger.info(
        "LLM call — provider=%s model=%s skill=%s wrapper=%s input_len=%d",
        provider.base_url,
        profile.model,
        skill.content[:40] if skill.content else "",
        wrapper.content[:40] if wrapper.content else "",
        len(raw_input),
    )

    body = build_request_body(
        profile, skill, wrapper, raw_input, get_global_system_prompt()
    )

    client = _get_openai_client(
        base_url=provider.base_url,
        api_key=provider.auth_token,
    )

    response = client.chat.completions.create(**body)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str):
        logger.error(
            "LLM returned empty response (finish_reason=%s)", choice.finish_reason
        )
        raise RuntimeError(
            f"LLM returned empty response (finish_reason: {choice.finish_reason})"
        )
    logger.info("LLM response — output_len=%d", len(content))
    return content
