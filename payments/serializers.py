from rest_framework import serializers


class PaystackWebhookSerializer(serializers.Serializer):
    event = serializers.CharField()
    payload = serializers.DictField()

    def to_internal_value(self, data):
        if isinstance(data, dict) and "data" in data and "payload" not in data:
            data = {**data, "payload": data.get("data")}
        return super().to_internal_value(data)

    # Optional helpers for convenience
    @staticmethod
    def get_reference(payload: dict) -> str | None:
        return (payload.get("payload") or payload.get("data") or {}).get("reference")

    def validate(self, attrs):
        payload = attrs.get("payload") or {}
        ref = payload.get("reference")
        if not isinstance(ref, str) or not ref.strip():
            raise serializers.ValidationError({"data.reference": "required"})
        # Optional sanity checks (non-fatal if absent)
        amt = payload.get("amount")
        if amt is not None and not isinstance(amt, (int, float, str)):
            raise serializers.ValidationError({"data.amount": "invalid"})
        cur = payload.get("currency")
        if cur is not None and not isinstance(cur, str):
            raise serializers.ValidationError({"data.currency": "invalid"})
        status = payload.get("status")
        if status is not None and not isinstance(status, str):
            raise serializers.ValidationError({"data.status": "invalid"})
        return attrs
