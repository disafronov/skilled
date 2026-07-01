from unittest.mock import MagicMock

from django import forms
from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from apps.inference.admin import ProfileAdmin, ProviderAdmin
from apps.inference.models import Profile, Provider


class ProviderAdminTests(SimpleTestCase):
    def test_provider_admin_order_comes_from_model(self):
        admin = ProviderAdmin(Provider, AdminSite())

        self.assertEqual(
            admin.fieldsets,
            (
                (None, {"fields": ("name", "api_type", "base_url", "auth_token")}),
                ("Changes", {"fields": ("updated_at", "created_at")}),
            ),
        )
        self.assertEqual(admin.readonly_fields, ("updated_at", "created_at"))
        self.assertEqual(
            admin.list_display,
            ("name", "api_type", "base_url", "updated_at"),
        )

    def test_provider_form_orders_name_first_and_uses_acronym_labels(self):
        admin = ProviderAdmin(Provider, AdminSite())
        form_class = admin.get_form(MagicMock())
        form = form_class()

        self.assertEqual(
            list(form.fields),
            ["name", "api_type", "base_url", "auth_token"],
        )
        self.assertEqual(form.fields["api_type"].label, "API type")
        self.assertEqual(form.fields["base_url"].label, "Base URL")
        self.assertIsInstance(form.fields["base_url"].widget, forms.URLInput)
        self.assertEqual(
            form.fields["name"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )
        self.assertEqual(
            form.fields["api_type"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )

    def test_auth_token_uses_non_rendering_password_widget(self):
        provider = Provider(
            name="provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="secret-token",
        )
        provider.pk = 1  # simulate existing DB instance
        admin = ProviderAdmin(Provider, AdminSite())
        form_class = admin.get_form(MagicMock(), provider)
        form = form_class(instance=provider)
        widget = form.fields["auth_token"].widget

        self.assertIsInstance(widget, forms.PasswordInput)
        self.assertFalse(widget.render_value)
        self.assertFalse(form.fields["auth_token"].required)
        self.assertEqual(
            widget.attrs["placeholder"],
            "Already set. Enter a new value to replace it.",
        )
        self.assertEqual(form.fields["auth_token"].help_text, "")
        self.assertNotIn(
            "secret-token",
            widget.render("auth_token", provider.auth_token),
        )

    def test_auth_token_keeps_existing_value_when_left_empty(self):
        provider = Provider(
            name="provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="secret-token",
        )
        provider.pk = 1  # simulate existing DB instance
        admin = ProviderAdmin(Provider, AdminSite())
        form_class = admin.get_form(MagicMock(), provider)
        form = form_class(instance=provider)
        form.cleaned_data = {"auth_token": ""}

        cleaned = form.clean()
        self.assertNotIn("auth_token", cleaned)

    def test_auth_token_has_no_filled_marker_for_new_provider(self):
        provider = Provider(
            name="provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="",
        )
        admin = ProviderAdmin(Provider, AdminSite())
        form_class = admin.get_form(MagicMock(), provider)
        form = form_class(instance=provider)
        field = form.fields["auth_token"]

        self.assertTrue(field.required)
        self.assertNotIn("placeholder", field.widget.attrs)

    def test_auth_token_uses_entered_value_when_provided(self):
        provider = Provider(
            name="provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="secret-token",
        )
        admin = ProviderAdmin(Provider, AdminSite())
        form_class = admin.get_form(MagicMock(), provider)
        form = form_class(instance=provider)
        form.cleaned_data = {"auth_token": "new-value"}

        self.assertEqual(form.clean()["auth_token"], "new-value")


class ProfileAdminTests(SimpleTestCase):
    def test_profile_admin_order_comes_from_model(self):
        admin = ProfileAdmin(Profile, AdminSite())

        self.assertEqual(
            admin.fieldsets,
            (
                (
                    None,
                    {
                        "fields": (
                            "name",
                            "provider",
                            "model",
                            "temperature",
                            "top_p",
                            "max_output_tokens",
                            "reasoning_effort",
                            "response_format",
                        )
                    },
                ),
                ("Changes", {"fields": ("updated_at", "created_at")}),
            ),
        )
        self.assertEqual(admin.readonly_fields, ("updated_at", "created_at"))
        self.assertEqual(
            admin.list_display,
            (
                "name",
                "provider",
                "model",
                "temperature",
                "top_p",
                "max_output_tokens",
                "reasoning_effort",
                "updated_at",
            ),
        )

    def test_profile_form_orders_name_first(self):
        admin = ProfileAdmin(Profile, AdminSite())
        form_class = admin.get_form(MagicMock())
        form = form_class()

        self.assertEqual(
            list(form.fields),
            [
                "name",
                "provider",
                "model",
                "temperature",
                "top_p",
                "max_output_tokens",
                "reasoning_effort",
                "response_format",
            ],
        )
        self.assertEqual(
            form.fields["name"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )
        self.assertNotIn("style", form.fields["response_format"].widget.attrs)
