import base64
import json

import requests
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env

consumer_key = os.getenv("MPESA_CONSUMER_KEY")
consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
from django.http import HttpResponse
from django.shortcuts import render

from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient
appname = 'mpesa'

# Create your views here.

def trigger(request):
    cl = MpesaClient()
    phone_number = '254717815133'
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

def generate_access_token():
    try:
        credentials = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }
        response = requests.get(
            f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
            headers=headers,
        ).json()

        if "access_token" in response:
            return response["access_token"]
        else:
            raise Exception("Access token missing in response.")

    except requests.RequestException as e:
        raise Exception(f"Failed to connect to M-Pesa: {str(e)}")