import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.inference.models import Profile, Provider
from apps.library.models import Skill, Wrapper
from apps.llm.client import (
    _get_openai_client,
    build_request_body,
    call_llm,
    get_global_system_prompt,
)


class LlmCallTests(TestCase):
    def setUp(self):
        _get_openai_client.cache_clear()

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(name="llm-skill", content="s")
        cls.wrapper = Wrapper.objects.create(
            name="llm-wrapper",
            skill=cls.skill,
            content="w",
        )
        cls.provider = Provider.objects.create(
            name="llm-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        cls.profile = Profile.objects.create(
            provider=cls.provider,
            name="llm-profile",
            model="gpt-4o",
            response_format={"type": "json_object"},
        )

    @patch("apps.llm.client.get_global_system_prompt", return_value="policy")
    @patch("apps.llm.client.OpenAI")
    def test_call_llm_returns_first_choice_content(self, openai, get_prompt):
        client = openai.return_value
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))]
        )

        result = call_llm(
            self.provider,
            self.profile,
            self.skill,
            self.wrapper,
            "hello",
        )

        self.assertEqual(result, "answer")
        get_prompt.assert_called_once_with()
        openai.assert_called_once_with(
            base_url="https://example.com",
            api_key="tok",
        )
        client.chat.completions.create.assert_called_once()
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["response_format"],
            {"type": "json_object"},
        )

    @patch("apps.llm.client.get_global_system_prompt", return_value="policy")
    @patch("apps.llm.client.OpenAI")
    def test_call_llm_raises_when_content_is_none(self, openai, get_prompt):
        client = openai.return_value
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=None),
                    finish_reason="stop",
                )
            ]
        )

        with self.assertRaises(RuntimeError) as ctx:
            call_llm(self.provider, self.profile, self.skill, self.wrapper, "hello")

        self.assertIn("finish_reason: stop", str(ctx.exception))

    def test_global_system_prompt_resolves_relative_policy_file(self):
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            path = base_dir / "policy.md"
            path.write_text("Relative policy\n", encoding="utf-8")

            with patch.dict("os.environ", {"POLICY_FILE": "policy.md"}):
                with patch("apps.llm.client.settings.BASE_DIR", base_dir):
                    self.assertEqual(get_global_system_prompt(), "Relative policy")

    def test_global_system_prompt_returns_empty_on_directory_as_policy_file(self):
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            dir_path = base_dir / "policy.md"
            dir_path.mkdir()
            with patch("apps.llm.client.settings.BASE_DIR", base_dir):
                self.assertEqual(get_global_system_prompt(), "")

    def test_global_system_prompt_returns_empty_on_non_utf8_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "policy.md"
            path.write_bytes(b"\xff\xfe")
            with patch("apps.llm.client.settings.BASE_DIR", Path(tmpdir)):
                self.assertEqual(get_global_system_prompt(), "")


class OpenAiRequestAssemblyTests(TestCase):
    """Test that build_request_body produces correct OpenAI-compatible bodies."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(
            name="translate", content="Translate to French."
        )
        cls.wrapper = Wrapper.objects.create(
            name="strict",
            skill=cls.skill,
            content="Respond in JSON format.",
        )
        cls.provider = Provider.objects.create(
            name="openai-request-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        cls.profile = Profile.objects.create(
            provider=cls.provider,
            name="default",
            model="gpt-4o",
            temperature=0.7,
            top_p=None,
            max_output_tokens=500,
            reasoning_effort=None,
            response_format=None,
        )

    def test_basic_request_body(self):
        body = build_request_body(self.profile, self.skill, self.wrapper, "hello", "")
        self.assertEqual(body["model"], "gpt-4o")
        self.assertEqual(len(body["messages"]), 2)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn("Translate to French.", body["messages"][0]["content"])
        self.assertIn("Respond in JSON format.", body["messages"][0]["content"])
        self.assertEqual(body["messages"][1]["role"], "user")
        self.assertEqual(body["messages"][1]["content"], "hello")

    def test_temperature_included(self):
        body = build_request_body(self.profile, self.skill, self.wrapper, "hello", "")
        self.assertEqual(body["temperature"], 0.7)

    def test_max_tokens_mapped(self):
        body = build_request_body(self.profile, self.skill, self.wrapper, "hello", "")
        self.assertEqual(body["max_completion_tokens"], 500)

    def test_global_system_prompt_appended(self):
        body = build_request_body(
            self.profile,
            self.skill,
            self.wrapper,
            "hello",
            "You are a helpful assistant.",
        )
        system_content = body["messages"][0]["content"]
        self.assertIn("You are a helpful assistant.", system_content)

    def test_global_system_prompt_loaded_from_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "policy.md"
            path.write_text("Always be concise.\n", encoding="utf-8")

            with patch.dict(os.environ, {"POLICY_FILE": str(path)}):
                self.assertEqual(get_global_system_prompt(), "Always be concise.")

    def test_empty_global_system_prompt_file_returns_empty_string(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "policy.md"
            path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"POLICY_FILE": str(path)}):
                self.assertEqual(get_global_system_prompt(), "")

    def test_missing_global_system_prompt_file_returns_empty_string(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.md"

            with patch.dict(os.environ, {"POLICY_FILE": str(path)}):
                with self.assertLogs("apps.llm.client", level="WARNING") as logs:
                    self.assertEqual(get_global_system_prompt(), "")
                    self.assertIn("without global policy", logs.output[0])


class NullableProfileFieldOmissionTests(TestCase):
    """Test that null profile fields are omitted from the request body."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(name="s", content="s")
        cls.wrapper = Wrapper.objects.create(
            name="w",
            skill=cls.skill,
            content="w",
        )
        cls.provider = Provider.objects.create(
            name="nullable-profile-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        cls.profile_all_null = Profile.objects.create(
            provider=cls.provider,
            name="minimal",
            model="gpt-4o",
            temperature=None,
            top_p=None,
            max_output_tokens=None,
            reasoning_effort=None,
            response_format=None,
        )

    def test_only_model_and_messages(self):
        body = build_request_body(
            self.profile_all_null,
            self.skill,
            self.wrapper,
            "hello",
            "",
        )
        self.assertEqual(body["model"], "gpt-4o")
        self.assertIn("messages", body)
        self.assertNotIn("temperature", body)
        self.assertNotIn("top_p", body)
        self.assertNotIn("max_tokens", body)
        self.assertNotIn("reasoning_effort", body)
        self.assertNotIn("response_format", body)
