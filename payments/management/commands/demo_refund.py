# payments/management/commands/demo_refund.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import ForeignKey, IntegerField, CharField
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth import get_user_model
from uuid import uuid4

from payments.notify import emit_once, send_refund_email
from payments.models import Transaction
from payments.gateways import maybe_refund_duplicate_success

# ---- status helpers (schema-agnostic) ----
def _status_choices():
    try:
        field = Transaction._meta.get_field("status")
        return [c[0] for c in (field.choices or [])]
    except Exception:
        return []

def _pick_status(preferred):
    choices = _status_choices()
    lut = {c.upper(): c for c in choices}
    for cand in preferred:
        if cand.upper() in lut:
            return lut[cand.upper()]
    return preferred[0]

STATUS_SUCCEEDED = _pick_status(["SUCCEEDED", "SUCCESS", "PAID", "COMPLETED"])
STATUS_REFUNDED_DUPLICATE = _pick_status(["REFUNDED_DUPLICATE", "REFUNDED"])

# ---- order schema inference ----
def _infer_order_binding():
    try:
        f = Transaction._meta.get_field("order")
        if isinstance(f, ForeignKey):
            return "fk", "order_id"
    except FieldDoesNotExist:
        pass
    try:
        f = Transaction._meta.get_field("order_id")
        if isinstance(f, IntegerField):
            return "int", "order_id"
        if isinstance(f, CharField):
            return "char", "order_id"
    except FieldDoesNotExist:
        pass
    raise CommandError("Could not find 'order' FK or 'order_id' field on Transaction model.")

class Command(BaseCommand):
    help = "Demo: create 2 successes for one order; auto-refund the later one and email the customer."

    def add_arguments(self, parser):
        parser.add_argument("--order", required=True, help="Order PK (int) or code (str), depending on schema")
        parser.add_argument("--user-pk", type=int, help="Required if Transaction.user is NOT NULL")
        parser.add_argument("--amount", default="1500.00")
        parser.add_argument("--gateway", default="paystack")
        parser.add_argument("--method", default="card")

    def handle(self, *args, **opts):
        mode, field_name = _infer_order_binding()
        amount = opts["amount"]; gateway = opts["gateway"]; method = opts["method"]
        User = get_user_model()

        # Resolve order filter from --order
        order_arg = opts["order"]
        if mode in ("fk", "int"):
            try:
                order_val = int(order_arg)
            except ValueError:
                raise CommandError(f"--order must be an integer for schema '{mode}'")
        else:
            order_val = order_arg
        order_filter = {field_name: order_val}

        # Resolve user (handle NOT NULL)
        user_obj = None
        try:
            f_user = Transaction._meta.get_field("user")
            user_required = isinstance(f_user, ForeignKey) and not f_user.null
        except FieldDoesNotExist:
            user_required = False

        if user_required:
            if opts.get("user_pk") is not None:
                user_obj = User.objects.filter(pk=opts["user_pk"]).first()
                if not user_obj:
                    raise CommandError(f"No user found with pk={opts['user_pk']}")
            else:
                user_obj = (User.objects.filter(is_superuser=True).first()
                            or User.objects.first())
                if not user_obj:
                    raise CommandError("Transaction.user is NOT NULL. Provide --user-pk pointing to an existing user.")

        self.stdout.write(self.style.WARNING(f"Schema detected: {mode} on '{field_name}'"))
        self.stdout.write(self.style.WARNING(f"Creating two SUCCEEDED tx for {field_name}={order_val}..."))
        self.stdout.write(f"Resolved statuses -> SUCCEEDED='{STATUS_SUCCEEDED}', DUP_REFUND='{STATUS_REFUNDED_DUPLICATE}'")

        # Create two success transactions
        def new_tx():
            payload = dict(
                method=method,
                gateway=gateway,
                amount=amount,
                currency="KES",
                idempotency_key=str(uuid4()),
                reference=f"ORD-DEMO-{uuid4().hex[:8].upper()}",
                status=STATUS_SUCCEEDED,
                callback_received=True,
                signature_valid=True,
                verified=True,
                processed_at=timezone.now(),
            )
            payload.update(order_filter)
            if user_obj:
                payload["user_id"] = user_obj.id
            return Transaction.objects.create(**payload)

        tx1 = new_tx(); tx2 = new_tx()
        self.stdout.write(f"  1) {tx1.reference} -> {tx1.status}")
        self.stdout.write(f"  2) {tx2.reference} -> {tx2.status}")

        # Run duplicate-refund logic (uses dev stub if PAYMENTS_ALLOW_INSECURE_WEBHOOKS=1)
        self.stdout.write(self.style.WARNING("Running duplicate-refund logic..."))
        results = maybe_refund_duplicate_success(
            tx2, keep_earliest=True, refunded_status=STATUS_REFUNDED_DUPLICATE
        )

        # Normalize results to [{'tx_ref': str, 'refund_id': Optional[str], 'ok': bool}]
        norm = []
        for r in (results or []):
            if isinstance(r, dict):
                norm.append({
                    "tx_ref": r.get("tx_ref"),
                    "refund_id": r.get("refund_id"),
                    "ok": bool(r.get("ok")),
                })
            else:
                norm.append({"tx_ref": str(r), "refund_id": None, "ok": True})

        refunded_refs = [r["tx_ref"] for r in norm if r["ok"]]

        # Report
        kept = (Transaction.objects
                .filter(**order_filter, status=STATUS_SUCCEEDED)
                .order_by("processed_at", "id")
                .first())
        self.stdout.write(self.style.SUCCESS(f"Kept earliest: {kept.reference if kept else 'None'}"))
        self.stdout.write(self.style.SUCCESS(f"Refunded dups: {refunded_refs}"))

        # Email the customer for successful refunds
        to_email = getattr(user_obj, "email", None) or "test@example.com"
        if to_email:
            for r in norm:
                if r["ok"] and r["tx_ref"]:
                    emit_once(
                        event_key=f"refund_completed:{r['tx_ref']}",
                        user=user_obj,
                        channel="email",
                        payload={"order_id": order_val, "amount": str(amount), "refund_id": r["refund_id"]},
                        send_fn=lambda r=r: send_refund_email(to_email, order_val, amount, r["tx_ref"], "completed"),
                    )

        # Print final state
        final = list(
            Transaction.objects.filter(**order_filter)
            .order_by("processed_at", "id")
            .values("reference", "status", "amount", "gateway")
        )
        self.stdout.write(self.style.HTTP_INFO(f"Final state: {final}"))
        self.stdout.write(self.style.SUCCESS("Done"))
