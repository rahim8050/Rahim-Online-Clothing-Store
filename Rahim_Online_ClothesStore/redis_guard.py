from __future__ import annotations

import os
from typing import Iterable


def is_management_command(argv: Iterable[str]) -> bool:
    argv_list = list(argv)
    if not argv_list:
        return False
    base = os.path.basename(argv_list[0])
    return base in {"manage.py", "django-admin", "django-admin.py", "django"}


def should_require_redis(debug: bool, redis_url: str, argv: Iterable[str]) -> bool:
    if debug or redis_url:
        return False
    return not is_management_command(argv)


def validate_redis_url(debug: bool, redis_url: str, argv: Iterable[str]) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if should_require_redis(debug, redis_url, argv):
        raise RuntimeError(
            "REDIS_URL is required when DEBUG=False for runtime processes (web/worker). "
            "Set REDIS_URL in the environment to enable Channels and caching."
        )
