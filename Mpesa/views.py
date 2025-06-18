from django.shortcuts import render
from django_daraja.mpesa.core import MpesaClient
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
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


@csrf_exempt
def stk_callback(request):
    """Handles M-Pesa STK Push callback."""
    if request.method == 'POST':
        try:
            data = request.body.decode('utf-8') 
            print("M-Pesa Callback Data:", data) 
            
      
            
            return HttpResponse("OK", status=200)
        except Exception as e:
            print("Callback Error:", e)
            return HttpResponse("Error", status=400)
    return HttpResponse("Method Not Allowed", status=405)