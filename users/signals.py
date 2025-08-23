from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
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