from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from django.db.models.signals import pre_save, post_save
from django.apps import apps
from django.db import transaction
from notifications.services import create_and_push
from notifications.ws import push_to_user

import logging; logger = logging.getLogger(__name__)
@receiver(user_logged_in)
def restore_cart_session(sender, request, user, **kwargs):
    old_cart_id = request.session.get('cart_id_backup')
    current_cart_id = request.session.get('cart_id')

    if old_cart_id and not current_cart_id:
        request.session['cart_id'] = old_cart_id
        request.session.modified = True
        
        
def on_login(sender, user, request, **kwargs):
    backend = request.session.get('_auth_user_backend')
    ua = request.META.get('HTTP_USER_AGENT', '')
    ip = request.META.get('REMOTE_ADDR', '')
    logger.info("login user=%s backend=%s ip=%s ua=%s", user.pk, backend, ip, ua)


user_logged_in.connect(on_login)

user_logged_in.connect(on_login)





VendorApplication = apps.get_model("users", "VendorApplication")

@receiver(pre_save, sender=VendorApplication)
def stash_old_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = VendorApplication.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except VendorApplication.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=VendorApplication)
def notify_status(sender, instance, created, **kwargs):
    user = instance.user
    url = "/vendor/" if instance.status == getattr(VendorApplication, "APPROVED", "approved") else "/dashboard/"

    if created:
        create_and_push(
            user,
            title="Vendor application received",
            message="Thanks! Your application was submitted and is pending review.",
            level="info",
            url=url,
        )
        return

    old = getattr(instance, "_old_status", None)
    if not old or old == instance.status:
        return

    if instance.status.lower() == "approved":
        create_and_push(
            user,
            title="Vendor application approved ✅",
            message="Congratulations! Your vendor account is ready. Open your vendor dashboard to get started.",
            level="success",
            url="/vendor/",
        )
    elif instance.status.lower() == "rejected":
        reason = getattr(instance, "rejection_reason", "") or "Your application did not meet the requirements."
        create_and_push(
            user,
            title="Vendor application rejected",
            message=f"{reason}\n\nYou can revise your details and re-apply.",
            level="warning",
            url="/dashboard/",
        )


# Additional structured WS event after commit for UI consumers
@receiver(post_save, sender=VendorApplication)
def vendor_application_status_push(sender, instance, created, **kwargs):
    try:
        user_id = instance.user_id
    except Exception:
        return
    # Decide whether to emit
    changed = created or getattr(instance, "_old_status", None) not in (None, instance.status)

    if not changed:
        return

    def _after():
        push_to_user(user_id, {
            "type": "vendor_application.updated",
            "application_id": instance.pk,
            "status": instance.status,
            "message": f"Your vendor application is now '{instance.status}'." if not created else "Application submitted and pending review.",
        })

    transaction.on_commit(_after)

