from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient
import json

from .models import Order, Payment

# ✅ Initialize MpesaClient once
cl = MpesaClient()

@csrf_exempt
def trigger_stk_push(request):
    if request.method == 'POST':
        try:
            phone_number = request.POST.get('phone_number')
            order_id = request.POST.get('order_id')

            if not phone_number:
                return render(request, "orders/order_confirmation.html", {
                    "error": "Phone number is required"
                })
            if not order_id:
                return render(request, "orders/order_confirmation.html", {
                    "error": "Order ID is required"
                })

            # ✅ Fetch order and amount
            order = get_object_or_404(Order, id=order_id)
            amount = order.get_total_cost()
            account_reference = f'ORDER-{order.id}'
            transaction_desc = f'Payment for Order #{order.id}'
            callback_url = 'https://your-ngrok-url.ngrok-free.app/mpesa/callback/'

            # ✅ Initiate STK push
            response = cl.stk_push(
                phone_number,
                amount,
                account_reference,
                transaction_desc,
                callback_url
            )
            resp_json = response.json() if hasattr(response, 'json') else response

            if resp_json.get('ResponseCode') == '0':
                # ✅ Save Payment as PENDING
                Payment.objects.create(
                    order=order,
                    merchant_request_id=resp_json.get('MerchantRequestID'),
                    checkout_request_id=resp_json.get('CheckoutRequestID'),
                    amount=amount,
                    status='PENDING'
                )
                context = {
                    "message": "Order confirmed. Please check your phone to complete the payment.",
                    "order_reference": account_reference,
                    "amount": amount,
                    "phone_number": phone_number,
                    "transaction_description": transaction_desc
                }
                return render(request, "orders/order_confirmation.html", context)
            else:
                return render(request, "orders/order_confirmation.html", {
                    "error": "Unable to initiate M-Pesa payment",
                    "mpesa_error": resp_json
                })
        except Exception as e:
            return render(request, "orders/order_confirmation.html", {
                "error": str(e)
            })
    return render(request, "orders/order_confirmation.html", {
        "error": "Invalid request method"
    })

@csrf_exempt
def stk_callback(request):
    resp = json.loads(request.body)
    data = resp.get('Body', {}).get('stkCallback', {})

    if data.get('ResultCode') == 0:
        merchant_request_id = data.get('MerchantRequestID')
        checkout_request_id = data.get('CheckoutRequestID')
        code = ""

        for i in data.get('CallbackMetadata', {}).get('Item', []):
            if i.get('Name') == "MpesaReceiptNumber":
                code = i.get('Value')

        # ✅ Get Payment record and update
        try:
            payment = Payment.objects.get(
                merchant_request_id=merchant_request_id,
                checkout_request_id=checkout_request_id
            )
            payment.code = code
            payment.status = "COMPLETED"
            payment.save()
        except Payment.DoesNotExist:
            pass

    return HttpResponse("OK")
