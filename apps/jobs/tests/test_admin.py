from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.admin import JobAdmin
from apps.jobs.models import Job
from apps.library.models import Skill, Wrapper


class JobAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        skill = Skill.objects.create(name="s", content="s")
        wrapper = Wrapper.objects.create(name="w", content="w")
        provider = Provider.objects.create(
            name="p",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(name="pr", model="gpt-4o")
        bot = Bot.objects.create(
            name="b",
            telegram_api_token="telegram-token",
            provider=provider,
            profile=profile,
            skill=skill,
            wrapper=wrapper,
        )
        cls.job = Job.objects.create(
            bot=bot,
            reply_target="123",
            raw_input="hello",
            received_at=timezone.now(),
        )

    def test_job_admin_is_read_only(self):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request, self.job))
        self.assertFalse(admin.has_delete_permission(request, self.job))
