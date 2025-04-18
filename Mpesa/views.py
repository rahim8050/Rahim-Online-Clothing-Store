import json

from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient


# Create your views here.

def trigger_mpesa_payment(request):
    cl = MpesaClient()
    phone_number = '254769690483'
    amount = 1
    account_reference = '01-ABC'
    transaction_desc = 'Online Clothes Payment'
    callback_url = ' https://intent-in-katydid.ngrok-free.app/callback_mpesa_payment'
    response = cl.stk_push(phone_number, amount, account_reference, transaction_desc, callback_url)
    return HttpResponse(response)


@csrf_exempt
def callback_mpesa_payment(request):
    try:

        print("Received callback:", request.body.decode())
        return HttpResponse(status=200)
    except Exception as e:
        print("Callback error:", str(e))
        return HttpResponse(status=400)