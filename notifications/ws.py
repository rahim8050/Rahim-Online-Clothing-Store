from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def push_to_user(user_id: int, payload: dict):
    """Deliver JSON payload to the per-user group via Channels.

    Group name format: user_<pk>
    """
    try:
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"user_{int(user_id)}", {"type": "notify", "payload": payload or {}}
        )
    except Exception:
        # Be resilient in non-WS environments
        pass
