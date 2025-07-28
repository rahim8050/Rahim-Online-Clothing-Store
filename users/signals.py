from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

@receiver(user_logged_in)
def restore_cart_session(sender, request, user, **kwargs):
    old_cart_id = request.session.get('cart_id_backup')
    current_cart_id = request.session.get('cart_id')

    if old_cart_id and not current_cart_id:
        request.session['cart_id'] = old_cart_id
        request.session.modified = True
