from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.inference.models import Profile, Provider
from apps.library.models import Skill, Wrapper
from workers.llm import call_llm, get_global_system_prompt


class LlmCallTests(TestCase):
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

    @patch("workers.llm.get_global_system_prompt", return_value="policy")
    @patch("workers.llm.OpenAI")
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

    @patch("workers.llm.get_global_system_prompt", return_value="policy")
    @patch("workers.llm.OpenAI")
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
                with patch("workers.llm.settings.BASE_DIR", base_dir):
                    self.assertEqual(get_global_system_prompt(), "Relative policy")
