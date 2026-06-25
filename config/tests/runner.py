from django.test.runner import DiscoverRunner


class PytestTestRunner(DiscoverRunner):
    """
    Stub runner for `manage.py test`.

    This project runs tests via pytest (see `make test` / `make all`). Django's
    test runner is intentionally disabled to avoid divergent test execution
    paths and confusing results.
    """

    def run_tests(  # type: ignore[override]
        self, _test_labels: object, _extra_tests: object = None, **_kwargs: object
    ) -> None:
        raise SystemExit(
            "Django test runner is disabled in this project.\n"
            "Run tests with: `make test` (or `uv run pytest`).\n"
        )
