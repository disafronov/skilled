"""Tests for the ``exc_info=settings.DEBUG`` logging pattern."""

import logging
from io import StringIO

from django.conf import settings
from django.test import TestCase, override_settings


class ExcInfoBehaviourTests(TestCase):
    """``exc_info=settings.DEBUG`` — stacktraces visible only in debug mode."""

    def _output_for_debug(self, debug: bool) -> str:
        logger = logging.getLogger("engine.telegram.tasks")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.ERROR)
        logger.addHandler(handler)

        try:
            raise RuntimeError("simulated failure")
        except RuntimeError:
            with override_settings(DEBUG=debug):
                logger.exception(
                    "LLM worker: job %d failed: %s",
                    1,
                    "simulated failure",
                    exc_info=settings.DEBUG,
                )

        logger.removeHandler(handler)
        return stream.getvalue()

    def test_exc_info_when_debug_true(self):
        output = self._output_for_debug(debug=True)
        self.assertIn("Traceback", output)

    def test_exc_info_when_debug_false(self):
        output = self._output_for_debug(debug=False)
        self.assertNotIn("Traceback", output)
