from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .enums import TxnStatus
from .models import Transaction, AuditLog
from .services import process_success, process_failure


@shared_task
def reconcile_stale_transactions():
    cutoff = timezone.now() - timedelta(minutes=30)
    qs = Transaction.objects.filter(status=TxnStatus.PENDING, created_at__lt=cutoff)
    for txn in qs:
        # TODO: query gateway API to verify status
        # For now we assume failure
        process_failure(txn=txn, request_id="reconcile")
        AuditLog.log(event="RECONCILED", transaction=txn, order=txn.order)
    return qs.count()
