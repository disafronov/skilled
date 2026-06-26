from django.test import TestCase

from apps.library.models import Skill, Wrapper


class LibraryModelTests(TestCase):
    def test_skill_string_is_name(self):
        skill = Skill.objects.create(name="skill-name", content="s")

        self.assertEqual(str(skill), "skill-name")

    def test_wrapper_string_is_name(self):
        skill = Skill.objects.create(name="skill-name", content="s")
        wrapper = Wrapper.objects.create(
            name="wrapper-name",
            skill=skill,
            content="w",
        )

        self.assertEqual(str(wrapper), "wrapper-name")
