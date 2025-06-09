from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import  urlsafe_base64_encode, urlsafe_base64_decode
from django.views.generic import FormView
from django.http import HttpResponse
from django.core.mail import send_mail



from users.forms import RegisterUserForm
from emailverification.tokens import account_activation_token



# Create your views here.
def home (request):
    pass
class Login(LoginView):
    template_name = "users/accounts/login.html"
class Logout(LogoutView):
    next_page = "/"

class RegisterUser(FormView):
    template_name = "users/accounts/register.html"
    form_class = RegisterUserForm
    success_url = "/"

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        
        current_site = get_current_site(self.request)
        
        # Render both subject and message templates
        mail_subject = 'Activate your account'
        message = render_to_string("users/accounts/acc_activate_email.html", {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        })
        
        to_email = form.cleaned_data.get('email')
        email = EmailMessage(
            mail_subject,
            message,
            to=[to_email]
        )
        email.send()
        
        messages.success(self.request, "Please confirm your email address to complete the registration.")
        messages.success(self.request, f"Account created for {user.username}")
        
        
        return super().form_valid(form)

def profile(request):
    return render(request, 'users/accounts/profile.html')
# def activate(request, uidb64, token):
#     user =get_user_model() 
#     try:
#         uid = force_str(urlsafe_base64_encode(uidb64))
#         user = user.objects.get(pk=uid)
#     except (TypeError, ValueError, OverflowError, user.DoesNotExist):
#         user = None
#     if user is not None and account_activation_token.check_token(user, token):
#         user.is_active = True
#         user.save()
#         login(request, user)
#         messages.success(request, "Your account has been activated successfully.")
#         return render(request, 'users/accounts/activation_success.html')
#     else:
#         messages.error(request, "Activation link is invalid!")
#         return render(request, 'users/accounts/activation_invalid.html')




def activate(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        if not user.is_active:  # Only activate if not already active
            user.is_active = True
            user.save()
            login(request, user)
            messages.success(request, "Your account has been activated successfully.")
            return render(request, 'users/accounts/activation_success.html')
        else:
            messages.info(request, "Your account is already active.")
            return render(request, 'users/accounts/activation_success.html')
    else:
        messages.error(request, "Activation link is invalid or has expired!")
        return render(request, 'users/accounts/activation_invalid.html')
    
    
    
