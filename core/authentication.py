import base64
import hashlib
import hmac
from datetime import datetime, timezone, timedelta

from django.conf import settings
from django.core.cache import cache
from rest_framework import authentication, exceptions


class HMACAuthentication(authentication.BaseAuthentication):
    """Header-based HMAC auth for machine-to-machine reads.

    Headers:
      - X-Api-KeyId: public key id
      - X-Api-Timestamp: ISO8601 or seconds since epoch (UTC)
      - X-Api-Signature: hex hmac-sha256 over canonical string

    Canonical string:
      f"{timestamp}\n{method}\n{path}\n{sha256hex(body)}"

    API keys are defined in settings.API_KEYS as a dict:
      API_KEYS = {
        "keyid123": {"secret": "base64/hex/or-plain", "scopes": ["catalog:read"]},
      }

    This authenticator returns (None, {"key_id":..., "scopes":[...]}) on success,
    so it does not mark the request user as authenticated; use HasScope to grant access.
    """

    header_key = "HTTP_X_API_KEYID"
    header_ts = "HTTP_X_API_TIMESTAMP"
    header_sig = "HTTP_X_API_SIGNATURE"
    skew = timedelta(minutes=5)

    def authenticate(self, request):
        key_id = request.META.get(self.header_key)
        ts_raw = request.META.get(self.header_ts)
        sig_hex = request.META.get(self.header_sig)
        if not (key_id and ts_raw and sig_hex):
            return None  # not attempting HMAC

        cfg = getattr(settings, "API_KEYS", {}) or {}
        meta = cfg.get(key_id)
        if not meta:
            raise exceptions.AuthenticationFailed("Invalid API key id")

        secret = meta.get("secret")
        if not secret:
            raise exceptions.AuthenticationFailed("Invalid API key config")

        # parse timestamp
        try:
            if ts_raw.isdigit():
                ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
            else:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid timestamp format")

        now = datetime.now(timezone.utc)
        if abs(now - ts) > self.skew:
            raise exceptions.AuthenticationFailed("Timestamp outside allowed window")

        body = request.body or b""
        body_sha = hashlib.sha256(body).hexdigest()
        canonical = "\n".join([ts_raw, request.method.upper(), request.get_full_path(), body_sha])
        # secret may be base64/hex/plain; try best-effort decode
        key = _coerce_secret_bytes(secret)
        expect = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig_hex.lower()):
            raise exceptions.AuthenticationFailed("Bad signature")

        # replay guard (best-effort): key+ts+sig for TTL window
        cache_key = f"hmac:{key_id}:{ts_raw}:{sig_hex.lower()}"
        if cache.add(cache_key, 1, timeout=int(self.skew.total_seconds())) is False:
            raise exceptions.AuthenticationFailed("Replay detected")

        auth = {"key_id": key_id, "scopes": meta.get("scopes", [])}
        return (None, auth)


def _coerce_secret_bytes(secret: str) -> bytes:
    s = (secret or "").strip()
    # try base64
    try:
        return base64.b64decode(s, validate=True)
    except Exception:
        pass
    # try hex
    try:
        return bytes.fromhex(s)
    except Exception:
        pass
    return s.encode("utf-8")

