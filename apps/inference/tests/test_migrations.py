import importlib
from unittest import TestCase

migration = importlib.import_module(
    "apps.inference.migrations.0004_populate_profile_provider"
)


class AppsStub:
    def __init__(self, profile_model, provider_model):
        self.profile_model = profile_model
        self.provider_model = provider_model

    def get_model(self, app_label, model_name):
        if (app_label, model_name) == ("inference", "Profile"):
            return self.profile_model
        if (app_label, model_name) == ("inference", "Provider"):
            return self.provider_model
        raise LookupError(app_label, model_name)


class ProfileQuerySetStub:
    def __init__(self, has_null_profiles):
        self.has_null_profiles = has_null_profiles
        self.updated_provider = None

    def exists(self):
        return self.has_null_profiles

    def update(self, provider):
        self.updated_provider = provider


class ProfileManagerStub:
    def __init__(self, has_null_profiles):
        self.null_profiles = ProfileQuerySetStub(has_null_profiles)

    def filter(self, **kwargs):
        if kwargs != {"provider__isnull": True}:
            raise AssertionError(kwargs)
        return self.null_profiles


class ProviderQuerySetStub:
    def __init__(self, providers):
        self.providers = providers

    def __getitem__(self, key):
        return self.providers[key]


class ProviderManagerStub:
    def __init__(self, providers):
        self.providers = providers

    def all(self):
        return ProviderQuerySetStub(self.providers)


class MigrationTests(TestCase):
    def test_populate_profile_provider_returns_when_no_null_profiles(self):
        profile_model = type(
            "ProfileStub",
            (),
            {"objects": ProfileManagerStub(has_null_profiles=False)},
        )
        provider_model = type(
            "ProviderStub",
            (),
            {"objects": ProviderManagerStub([])},
        )
        apps = AppsStub(profile_model, provider_model)

        migration.assign_existing_profiles_to_provider(apps, None)

        self.assertIsNone(profile_model.objects.null_profiles.updated_provider)

    def test_populate_profile_provider_assigns_single_provider(self):
        provider = object()
        profile_model = type(
            "ProfileStub",
            (),
            {"objects": ProfileManagerStub(has_null_profiles=True)},
        )
        provider_model = type(
            "ProviderStub",
            (),
            {"objects": ProviderManagerStub([provider])},
        )
        apps = AppsStub(profile_model, provider_model)

        migration.assign_existing_profiles_to_provider(apps, None)

        self.assertIs(profile_model.objects.null_profiles.updated_provider, provider)

    def test_populate_profile_provider_rejects_ambiguous_provider_count(self):
        profile_model = type(
            "ProfileStub",
            (),
            {"objects": ProfileManagerStub(has_null_profiles=True)},
        )
        provider_model = type(
            "ProviderStub",
            (),
            {"objects": ProviderManagerStub([object(), object()])},
        )
        apps = AppsStub(profile_model, provider_model)

        with self.assertRaises(RuntimeError):
            migration.assign_existing_profiles_to_provider(apps, None)
