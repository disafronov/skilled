from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from apps.library.admin import SkillAdmin, WrapperAdmin
from apps.library.models import Skill, Wrapper


class SkillAdminTests(SimpleTestCase):
    def test_skill_admin_order_comes_from_model(self):
        admin = SkillAdmin(Skill, AdminSite())

        self.assertEqual(admin.fields, ("name", "content", "updated_at", "created_at"))
        self.assertEqual(admin.readonly_fields, ("updated_at", "created_at"))
        self.assertEqual(admin.list_display, ("name", "updated_at"))

    def test_skill_form_orders_name_first_and_keeps_content_textarea(self):
        admin = SkillAdmin(Skill, AdminSite())
        form_class = admin.get_form(MagicMock())
        form = form_class()

        self.assertEqual(list(form.fields), ["name", "content"])
        self.assertEqual(
            form.fields["name"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )
        self.assertNotIn("style", form.fields["content"].widget.attrs)


class WrapperAdminTests(SimpleTestCase):
    def test_wrapper_admin_order_comes_from_model(self):
        admin = WrapperAdmin(Wrapper, AdminSite())

        self.assertEqual(
            admin.fields,
            ("name", "skill", "content", "updated_at", "created_at"),
        )
        self.assertEqual(admin.readonly_fields, ("updated_at", "created_at"))
        self.assertEqual(admin.list_display, ("name", "skill", "updated_at"))

    def test_wrapper_form_orders_name_first_and_keeps_content_textarea(self):
        admin = WrapperAdmin(Wrapper, AdminSite())
        form_class = admin.get_form(MagicMock())
        form = form_class()

        self.assertEqual(list(form.fields), ["name", "skill", "content"])
        self.assertEqual(
            form.fields["name"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )
        self.assertEqual(
            form.fields["skill"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )
        self.assertNotIn("style", form.fields["content"].widget.attrs)
