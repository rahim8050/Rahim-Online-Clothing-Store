import os
from django.conf import settings


def test_channel_layer_uses_redis_when_url_is_set(settings, monkeypatch):
    # Simulate REDIS_URL present before settings import
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    # Reload our module under test
    from importlib import reload
    import Rahim_Online_ClothesStore.settings as s
    reload(s)

    assert s.CHANNEL_LAYERS["default"]["BACKEND"] == "channels_redis.core.RedisChannelLayer"
    assert s.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"] == ["redis://localhost:6379/0"]


def test_channel_layer_defaults_to_inmemory_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from importlib import reload
    import Rahim_Online_ClothesStore.settings as s
    reload(s)
    assert s.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer"

