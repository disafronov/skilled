from django.db import IntegrityError
from django.test import TestCase

from apps.inference.models import Profile, Provider


class InferenceModelTests(TestCase):
    def test_provider_string_is_name(self):
        provider = Provider.objects.create(
            name="provider-name",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )

        self.assertEqual(str(provider), "provider-name")

    def test_profile_string_is_name(self):
        provider = Provider.objects.create(
            name="profile-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(
            provider=provider,
            name="profile-name",
            model="gpt-4o",
        )

        self.assertEqual(str(profile), "profile-name")

    def test_profile_name_is_unique_per_provider(self):
        provider = Provider.objects.create(
            name="profile-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        other_provider = Provider.objects.create(
            name="other-provider",
            api_type="openai",
            base_url="https://other.example.com",
            auth_token="tok",
        )

        Profile.objects.create(provider=provider, name="default", model="gpt-4o")
        Profile.objects.create(
            provider=other_provider,
            name="default",
            model="gpt-4o",
        )

        with self.assertRaises(IntegrityError):
            Profile.objects.create(provider=provider, name="default", model="gpt-4o")
