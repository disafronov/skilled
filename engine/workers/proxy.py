"""Proxy functions that defer to user-configurable task targets.

Keeps engine/ free of hardcoded references to apps/ modules.
The target function path is configured via settings.Q2_WORKER_FUNC.
When unset, acts as a no-op echo — returns the first argument as-is.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string


def worker(*args: Any, **kwargs: Any) -> Any:
    """Call the configured Q2 worker function, or echo if unconfigured."""
    func_path = settings.Q2_WORKER_FUNC
    if func_path:
        func = import_string(func_path)
        return func(*args, **kwargs)
    return args[0] if args else None
