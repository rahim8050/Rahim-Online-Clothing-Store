from django.shortcuts import render
from django_daraja.mpesa.core import MpesaClient
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from django.contrib import messages
import json
from django.shortcuts import redirect 


  

from django.shortcuts import get_object_or_404
from orders.models import Order
from Mpesa.models import Payment
from django.views.decorators.csrf import csrf_exempt
import json


# Initialize MpesaClient once (avoid re-initializing in every request)
cl = MpesaClient()



@csrf_exempt

def trigger_stk_push(request):
    if request.method == 'POST':
        try:
            # Get phone number from form or JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                phone_number = data.get('phone_number')
            else:
                phone_number = request.POST.get('phone_number')

            if not phone_number:
                return JsonResponse({'error': 'Phone number is required'}, status=400)

            amount = 1
            account_reference = 'ORDER-01'
            transaction_desc = 'Payment for Clothes'
            callback_url = 'https://your-ngrok-url.ngrok-free.app/mpesa/callback/'

            # Initiate STK push
            response = cl.stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
                callback_url=callback_url
            )

            # Parse response to dict if necessary
            return JsonResponse(response.json())  # Or use .to_dict() if available

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# @csrf_exempt
# def trigger_stk_push(request):
#     try:
#         phone_number = '254769690483'
#         amount = 1  
#         account_reference = 'ORDER-01'  
#         transaction_desc = 'Payment for Clothes'
#         callback_url = 'https://your-ngrok-url.ngrok-free.app/mpesa/callback/'

#         # Initiate STK push
#         response = cl.stk_push(
#             phone_number=phone_number,
#             amount=amount,
#             account_reference=account_reference,
#             transaction_desc=transaction_desc,
#             callback_url=callback_url
#         )

   
#         return JsonResponse(response.json())  

      

#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)
# @csrf_exempt
# def trigger_stk_push(request):
#     try:
#         phone_number = '254769690483'
#         amount = 1  
#         account_reference = 'ORDER-01'  
#         transaction_desc = 'Payment for Clothes'
#         callback_url = 'https://your-ngrok-url.ngrok-free.app/mpesa/callback/'

#         # Initiate STK push
#         response = cl.stk_push(
#             phone_number=phone_number,
#             amount=amount,
#             account_reference=account_reference,
#             transaction_desc=transaction_desc,
#             callback_url=callback_url
#         )
        
#         return JsonResponse(response, safe=False)  # Returns raw Safaricom response
    
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)

def trigger_stk_push(request,order_id):
    from orders.models import Transaction 
    transaction = Transaction.objects.get(id=order_id)
    total = transaction.get_total_cost()
    phone = transaction.phone.order.phone
    phone_number = '254769690483'
    amount = 1  
    account_reference = transaction.user.username  
    transaction_desc = 'Payment for Clothes'
    callback_url = 'https://your-ngrok-url.ngrok-free.app/mpesa/callback/'
    if response.response_code == '0':
        payment = payment.objects.create(transaction=transaction,
                                         merchant_request_id=response.merchant_request_id,
                                         checkout_request_id=response.checkout_request_id,
                                        
                                         )
        payment.save()
        messages.success(request, 'Payment initiated successfully.')

        # Initiate STK push
    response = cl.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=transaction.account_reference,
            transaction_desc='Payment for Clothes',
            callback_url=callback_url
        )
        
    return redirect('mpesa:mpesa', order_id=order_id)



@csrf_exempt
def stk_callback(request):
    """Handles M-Pesa STK Push callback."""
    resp = json.loads(request.body)
    data = resp['Body']['stkCallback']
    if data["ResultCode"] == "0":
        m_id = data["MerchantRequestID"]
        c_id = data["CheckoutRequestID"]
        code =""
        item = data["CallbackMetadata"]["Item"]
        for i in item:
            name = i["Name"]
            if name == "MpesaReceiptNumber":
                code= i["Value"]
        from orders.models import Transaction
        transaction = Transaction.objects.get(merchant_request_id=m_id, checkout_request_id=c_id)
        transaction.code = code
        transaction.status = "COMPLETED"
        transaction.save()
    return HttpResponse("OK")
# def mpesa_payment  (request,order_id):
#     transaction = Transaction.objects.get(id=order_id)
#     total = transaction.get_total_cost()
    
    
#     return render(request, 'mpesa/payment.html')
def mpesa(request):
    """Renders the M-Pesa payment page."""
    return render(request, 'mpesa/index.html', {
        'title': 'M-Pesa Payment',
        'description': 'Pay for your order using M-Pesa'
    })