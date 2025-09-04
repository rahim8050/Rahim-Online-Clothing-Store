# notifications/services.py
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from .ws import push_to_user
from .models import Notification

def create_and_push(user, title, message, level="info", url=""):
    # Save in DB
    Notification.objects.create(user=user, title=title, message=message, level=level, url=url)

    # Email (best-effort)
    if getattr(user, "email", None):
        html = render_to_string("emails/generic.html", {"user": user, "title": title, "message": message, "cta_url": url})
        try:
            send_mail(subject=title, message=message, from_email=settings.DEFAULT_FROM_EMAIL,
                      recipient_list=[user.email], html_message=html, fail_silently=True)
        except Exception:
            pass

    # WebSocket push (generic notification payload via per-user group)
    try:
        push_to_user(user.id, {"type": "notify", "title": title, "message": message, "level": level, "url": url})
    except Exception:
        pass


def send_sms(phone, text):
    # integrate Africa's Talking/Twilio here
    pass
