# payments/senders.py
from django.core.mail import send_mail


def send_refund_email(to_email, order_no, amount, reference, stage):
    subject = f"Refund {stage} for Order {order_no}"
    body = f"Hi, your refund for {order_no} ({amount}) is {stage}. Ref: {reference}."
    send_mail(subject, body, None, [to_email], fail_silently=False)


def send_sms(to_msisdn, msg):
    # integrate Twilio, Africa's Talking, etc.
    # twilio_client.messages.create(to=to_msisdn, from_=TWILIO_FROM, body=msg)
    pass
