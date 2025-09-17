import pytest
from django.contrib.auth import get_user_model
from django.db import transaction as dj_transaction
from users.models import VendorApplication


@pytest.mark.django_db
def test_vendor_application_signal_calls_push(monkeypatch):
    # Make on_commit run immediately so our assertions see the push
    # Patch both local import and the one inside users.signals
    monkeypatch.setattr(dj_transaction, "on_commit", lambda f: f())
    monkeypatch.setattr('users.signals.transaction.on_commit', lambda f: f())

    called = {}

    def fake_push(uid, payload):
        called['uid'] = uid
        called['payload'] = payload

    monkeypatch.setattr('users.signals.push_to_user', fake_push)

    U = get_user_model()
    user = U.objects.create_user(username='x', password='p')

    # Create -> should push vendor_application.updated for pending
    app = VendorApplication.objects.create(user=user)
    assert called['uid'] == user.id
    assert called['payload']['type'] == 'vendor_application.updated'
    assert called['payload']['status'] == app.status

    # Change status -> sends again
    called.clear()
    app.status = VendorApplication.APPROVED
    app.save()
    assert called['uid'] == user.id
    assert called['payload']['status'] == 'approved'
