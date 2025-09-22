import hashlib
import json

from django.db import migrations
from django.db.utils import IntegrityError


def backfill(apps, schema_editor):
    Tx = apps.get_model("orders", "Transaction")
    for t in Tx.objects.filter(body_sha256__isnull=True):
        raw = getattr(t, "raw_event", None)
        if not raw:
            continue
        try:
            # Best-effort stable representation from JSONField
            body = json.dumps(raw, separators=(",", ":"), sort_keys=True).encode("utf-8")
            sha = hashlib.sha256(body).hexdigest().lower()
            t.body_sha256 = sha
            try:
                t.save(update_fields=["body_sha256"])
            except IntegrityError:
                # Duplicate SHA across rows — skip to keep migration non-blocking
                t.body_sha256 = None
        except Exception:
            continue


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0012_transaction_body_sha256"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
