from channels.generic.websocket import AsyncJsonWebsocketConsumer

class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.delivery_id = self.scope["url_route"]["kwargs"]["delivery_id"]
        # Align with Delivery.ws_group (e.g., "delivery.123")
        self.group_name = f"delivery.{self.delivery_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    # Allow manual test from browser: ws.send(JSON.stringify({...}))
    async def receive_json(self, content, **kwargs):
        """
        Accept both legacy and current payload shapes and broadcast to the group:
        - {"type":"position_update", "lat": ..., "lng": ...}
        - {"op":"update", "lat": ..., "lng": ..., "status": "..."}
        - {"type":"status", "status": "picked_up"}
        - {"op":"ping"}
        """
        msg_type = content.get("type") or content.get("op")

        if msg_type in ("position_update", "update", "position"):
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "delivery.event",
                    "kind": "position_update",
                    "lat": content.get("lat"),
                    "lng": content.get("lng"),
                    # optional passthroughs
                    "status": content.get("status"),
                    "eta": content.get("eta"),
                },
            )
            return

        if msg_type == "status":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "delivery.event",
                    "kind": "status",
                    "status": content.get("status"),
                },
            )
            return

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

    # Canonical group event -> fan out to clients in the expected shape
    async def delivery_event(self, event):
        kind = event.get("kind")
        if kind == "position_update":
            await self.send_json(
                {
                    "type": "position_update",
                    "lat": event.get("lat"),
                    "lng": event.get("lng"),
                    # optional passthroughs
                    "status": event.get("status"),
                    "ts": event.get("ts"),
                }
            )
            return

        if kind == "status":
            await self.send_json({"type": "status", "status": event.get("status")})
            return

    # Back-compat for older senders using type="tracker.update"
    async def tracker_update(self, event):
        data = event.get("data", {})
        await self.send_json({"type": "position_update", **data})

    # Back-compat for staff debug sender using type="broadcast"
    async def broadcast(self, event):
        payload = event.get("payload") or {}
        await self.send_json(payload)
