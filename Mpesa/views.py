from django.shortcuts import render
from django_daraja.mpesa.core import MpesaClient
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

# Initialize MpesaClient once (avoid re-initializing in every request)
cl = MpesaClient()

@csrf_exempt
def trigger_stk_push(request):
    try:
        phone_number = '254769690483'
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
        
        return JsonResponse(response, safe=False)  # Returns raw Safaricom response
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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