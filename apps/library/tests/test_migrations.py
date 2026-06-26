import importlib
from unittest import TestCase

migration = importlib.import_module(
    "apps.library.migrations.0003_populate_wrapper_skill"
)


class AppsStub:
    def __init__(self, bot_model, skill_model, wrapper_model):
        self.bot_model = bot_model
        self.skill_model = skill_model
        self.wrapper_model = wrapper_model

    def get_model(self, app_label, model_name):
        if (app_label, model_name) == ("bots", "Bot"):
            return self.bot_model
        if (app_label, model_name) == ("library", "Skill"):
            return self.skill_model
        if (app_label, model_name) == ("library", "Wrapper"):
            return self.wrapper_model
        raise LookupError(app_label, model_name)


class WrapperStub:
    def __init__(self, pk):
        self.pk = pk
        self.skill = None
        self.skill_id = None
        self.saved_fields = None

    def save(self, update_fields):
        self.saved_fields = update_fields


class WrapperManagerStub:
    def __init__(self, wrappers):
        self.wrappers = wrappers

    def filter(self, **kwargs):
        if kwargs != {"skill__isnull": True}:
            raise AssertionError(kwargs)
        return self.wrappers


class SkillQuerySetStub:
    def __init__(self, skills):
        self.skills = skills

    def __getitem__(self, key):
        return self.skills[key]


class SkillManagerStub:
    def __init__(self, skills):
        self.skills = skills

    def all(self):
        return SkillQuerySetStub(self.skills)


class BotSkillQuerySetStub:
    def __init__(self, skill_ids):
        self.skill_ids = skill_ids

    def order_by(self, field_name):
        if field_name != "skill_id":
            raise AssertionError(field_name)
        return self

    def values_list(self, field_name, flat):
        if field_name != "skill_id" or flat is not True:
            raise AssertionError(field_name, flat)
        return self

    def distinct(self):
        return self

    def __getitem__(self, key):
        return self.skill_ids[key]


class BotManagerStub:
    def __init__(self, wrapper_skill_ids):
        self.wrapper_skill_ids = wrapper_skill_ids

    def filter(self, **kwargs):
        wrapper = kwargs["wrapper"]
        return BotSkillQuerySetStub(self.wrapper_skill_ids.get(wrapper.pk, []))


class MigrationTests(TestCase):
    def test_populate_wrapper_skill_assigns_bot_skill(self):
        wrapper = WrapperStub(pk=1)
        apps = AppsStub(
            bot_model=type(
                "BotStub",
                (),
                {"objects": BotManagerStub({wrapper.pk: [7]})},
            ),
            skill_model=type("SkillStub", (), {"objects": SkillManagerStub([])}),
            wrapper_model=type(
                "WrapperStubModel",
                (),
                {"objects": WrapperManagerStub([wrapper])},
            ),
        )

        migration.assign_existing_wrappers_to_skills(apps, None)

        self.assertEqual(wrapper.skill_id, 7)
        self.assertEqual(wrapper.saved_fields, ["skill"])

    def test_populate_wrapper_skill_rejects_multiple_bot_skills(self):
        wrapper = WrapperStub(pk=1)
        apps = AppsStub(
            bot_model=type(
                "BotStub",
                (),
                {"objects": BotManagerStub({wrapper.pk: [7, 8]})},
            ),
            skill_model=type("SkillStub", (), {"objects": SkillManagerStub([])}),
            wrapper_model=type(
                "WrapperStubModel",
                (),
                {"objects": WrapperManagerStub([wrapper])},
            ),
        )

        with self.assertRaises(RuntimeError):
            migration.assign_existing_wrappers_to_skills(apps, None)

    def test_populate_wrapper_skill_assigns_single_global_skill_for_orphan(self):
        skill = object()
        wrapper = WrapperStub(pk=1)
        apps = AppsStub(
            bot_model=type(
                "BotStub",
                (),
                {"objects": BotManagerStub({wrapper.pk: []})},
            ),
            skill_model=type("SkillStub", (), {"objects": SkillManagerStub([skill])}),
            wrapper_model=type(
                "WrapperStubModel",
                (),
                {"objects": WrapperManagerStub([wrapper])},
            ),
        )

        migration.assign_existing_wrappers_to_skills(apps, None)

        self.assertIs(wrapper.skill, skill)
        self.assertEqual(wrapper.saved_fields, ["skill"])

    def test_populate_wrapper_skill_rejects_ambiguous_orphan_skill_count(self):
        wrapper = WrapperStub(pk=1)
        apps = AppsStub(
            bot_model=type(
                "BotStub",
                (),
                {"objects": BotManagerStub({wrapper.pk: []})},
            ),
            skill_model=type(
                "SkillStub",
                (),
                {"objects": SkillManagerStub([object(), object()])},
            ),
            wrapper_model=type(
                "WrapperStubModel",
                (),
                {"objects": WrapperManagerStub([wrapper])},
            ),
        )

        with self.assertRaises(RuntimeError):
            migration.assign_existing_wrappers_to_skills(apps, None)
