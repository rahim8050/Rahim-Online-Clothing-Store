import pytest

from Rahim_Online_ClothesStore.redis_guard import (
    should_require_redis,
    validate_redis_url,
)


def test_validate_redis_url_requires_for_runtime(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL is required"):
        validate_redis_url(False, "", ["daphne"])


def test_validate_redis_url_skips_for_management_command(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    validate_redis_url(False, "", ["manage.py", "collectstatic"])


def test_should_require_redis_skips_when_url_present():
    assert should_require_redis(False, "redis://localhost:6379/0", ["daphne"]) is False
