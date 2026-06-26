from unittest.mock import MagicMock

from django import forms
from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from apps.inference.admin import ProviderAdmin
from apps.inference.models import Provider


class ProviderAdminTests(SimpleTestCase):
    def test_auth_token_uses_non_rendering_password_widget(self):
        provider = Provider(
            name="provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="secret-token",
        )
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
        admin = ProviderAdmin(Provider, AdminSite())
        form_class = admin.get_form(MagicMock(), provider)
        form = form_class(instance=provider)
        form.cleaned_data = {"auth_token": ""}

        self.assertEqual(form.clean()["auth_token"], "secret-token")

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
