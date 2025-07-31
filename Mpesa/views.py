from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient
import json
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from orders.models import Order, Transaction
from .models import Payment
import traceback

# Initialize MpesaClient once
cl = MpesaClient()

@csrf_exempt
def daraja_stk_push(request):
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

            order = get_object_or_404(Order, id=order_id)
            amount = order.get_total_cost()
            account_reference = f'ORDER-{order.id}'
            transaction_desc = f'Payment for Order #{order.id}'
            callback_url = 'https://intent-in-katydid.ngrok-free.app/mpesa/callback/'  

            # Initiate STK Push
            response = cl.stk_push(
                phone_number,
                amount,
                account_reference,
                transaction_desc,
                callback_url
            )

            # Debug print response
            resp_json = response.json() if hasattr(response, 'json') else response
            print("MPESA STK Response:", resp_json)

            if resp_json.get('ResponseCode') == '0':
                payment = Payment.objects.create(
                    order=order,
                    merchant_request_id=resp_json.get('MerchantRequestID'),
                    checkout_request_id=resp_json.get('CheckoutRequestID'),
                    amount=amount,
                    status='PENDING'
                )
                Transaction.objects.create(
                    user=order.user,
                    amount=amount,
                    method="mpesa",
                    gateway="daraja",
                    status="pending",
                    reference=payment.checkout_request_id,
                )
                return render(request, "orders/order_confirmation.html", {
                    "message": "STK Push sent. Check your phone to complete the payment.",
                    "order_reference": account_reference,
                    "amount": amount,
                    "phone_number": phone_number
                })
            else:
                return render(request, "orders/order_confirmation.html", {
                    "error": "Failed to initiate M-Pesa payment.",
                    "mpesa_error": resp_json
                })

        except Exception as e:
            traceback.print_exc()
            return render(request, "orders/order_confirmation.html", {
                "error": f"An error occurred: {str(e)}"
            })

    return render(request, "orders/order_confirmation.html", {
        "error": "Invalid request method."
    })
@csrf_exempt
def stk_callback(request):
    try:
        resp = json.loads(request.body)
        data = resp.get('Body', {}).get('stkCallback', {})
        result_code = data.get('ResultCode', -1)

        if result_code == 0:  # pyPayment successful
            merchant_request_id = data.get('MerchantRequestID')
            checkout_request_id = data.get('CheckoutRequestID')

            # Extract MpesaReceiptNumber safely
            mpesa_receipt = next(
                (item["Value"] for item in data.get("CallbackMetadata", {}).get("Item", [])
                 if item.get("Name") == "MpesaReceiptNumber"),
                ""
            )

            try:
                #  Find the matching payment
                payment = Payment.objects.get(
                    merchant_request_id=merchant_request_id,
                    checkout_request_id=checkout_request_id
                )
                payment.code = mpesa_receipt
                payment.status = "COMPLETED"
                payment.save()
                Transaction.objects.filter(reference=checkout_request_id).update(status="success")

                #  Mark order as paid
                order = payment.order
                order.paid = True
                order.save()

                user = order.user

                #  Compose and send confirmation email
                subject = "Your Order Payment Was Successful"
                message = (
                    f"Hi {user.username},\n\n"
                    f"We've received your payment for Order #{order.id}.\n"
                    f"Amount paid: KES {payment.amount}\n"
                    f"Transaction code: {mpesa_receipt}\n\n"
                    f"Your order is being processed and we'll update you on its status.\n\n"
                    f"Thank you for shopping with us!\n\n"
                    f"- The Rahim Online Clothing Store Team"
                )
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False
                )

            except Payment.DoesNotExist:
                print(
                    f"[ERROR] Payment not found for MerchantRequestID={merchant_request_id}, CheckoutRequestID={checkout_request_id}"
                )
        else:
            print(f"[INFO] STK Push failed with ResultCode={result_code}")

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode error in stk_callback: {e}")

    return HttpResponse("OK")




# @csrf_exempt
# def stk_callback(request):
#     try:
#         resp = json.loads(request.body)
#         data = resp.get('Body', {}).get('stkCallback', {})
#         result_code = data.get('ResultCode', -1)

#         if result_code == 0:
#             merchant_request_id = data.get('MerchantRequestID')
#             checkout_request_id = data.get('CheckoutRequestID')

#             mpesa_receipt = next(
#                 (item["Value"] for item in data.get("CallbackMetadata", {}).get("Item", [])
#                  if item.get("Name") == "MpesaReceiptNumber"),
#                 ""
#             )

#             try:
#                 payment = Payment.objects.get(
#                     merchant_request_id=merchant_request_id,
#                     checkout_request_id=checkout_request_id
#                 )
#                 payment.code = mpesa_receipt
#                 payment.status = "COMPLETED"
#                 payment.save()

#                 order = payment.order
#                 order.paid = True
#                 order.save()

#                 user = order.user

#                 subject = "Your Order Payment Was Successful"

#                 # Render HTML email template
#                 message = render_to_string('Mpesa/mpesa/payment.html', {
#                     'user': user,
#                     'order': order,
#                     'payment': payment
#                 })

#                 email = EmailMessage(
#                     subject,
#                     message,
#                     settings.DEFAULT_FROM_EMAIL,
#                     [user.email]
#                 )
#                 email.content_subtype = 'html'
#                 email.send()

#             except Payment.DoesNotExist:
#                 print(f"[ERROR] Payment not found for MerchantRequestID={merchant_request_id}, CheckoutRequestID={checkout_request_id}")

#         else:
#             print(f"[INFO] STK Push failed with ResultCode={result_code}")

#     except json.JSONDecodeError as e:
#         print(f"[ERROR] JSON decode error in stk_callback: {e}")
#     except Exception as e:
#         print(f"[GENERAL ERROR] {e}")

#     return HttpResponse("OK")



