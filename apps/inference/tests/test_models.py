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
        profile = Profile.objects.create(name="profile-name", model="gpt-4o")

        self.assertEqual(str(profile), "profile-name")
