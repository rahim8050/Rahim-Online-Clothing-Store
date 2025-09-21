from rest_framework import serializers


class PaystackWebhookSerializer(serializers.Serializer):
    event = serializers.CharField()
    data = serializers.DictField()

    # Optional helpers for convenience
    @staticmethod
    def get_reference(payload: dict) -> str | None:
        return (payload.get("data") or {}).get("reference")

    def validate(self, attrs):
        data = attrs.get("data") or {}
        ref = data.get("reference")
        if not isinstance(ref, str) or not ref.strip():
            raise serializers.ValidationError({"data.reference": "required"})
        # Optional sanity checks (non-fatal if absent)
        amt = data.get("amount")
        if amt is not None and not isinstance(amt, (int, float, str)):
            raise serializers.ValidationError({"data.amount": "invalid"})
        cur = data.get("currency")
        if cur is not None and not isinstance(cur, str):
            raise serializers.ValidationError({"data.currency": "invalid"})
        status = data.get("status")
        if status is not None and not isinstance(status, str):
            raise serializers.ValidationError({"data.status": "invalid"})
        return attrs
