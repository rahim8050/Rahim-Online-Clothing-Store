import json

from django.http import HttpResponse
from django.shortcuts import render

from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient
appname = 'mpesa'

# Create your views here.

def trigger(request):
    cl = MpesaClient()
    phone_number = '254769690483'
    amount = 1
    account_reference = '01-ABC'
    transaction_desc = 'Online Clothes Payment'
    callback_url = 'https://intent-in-katydid.ngrok-free.app/mpesa/callback-handler'
    response = cl.stk_push(phone_number, amount, account_reference, transaction_desc, callback_url)
    return HttpResponse(response)


@csrf_exempt
def callback(request):
    print("Raw callback data:", request.body.decode())
    return HttpResponse("OK", status=200)


def mpesa(request):
    return render(request, 'index.html')