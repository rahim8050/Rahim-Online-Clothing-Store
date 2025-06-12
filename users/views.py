from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.urls import reverse_lazy
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import  urlsafe_base64_encode, urlsafe_base64_decode
from django.views.generic import FormView
from django.db import IntegrityError
from users.forms import RegisterUserForm
from users.models import CustomUser
from django.shortcuts import render, redirect
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from .tokens import account_activation_token
from .forms import ResendActivationEmailForm
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
# Create your views here.
def home (request):
    pass
class Login(LoginView):
    template_name = "users/accounts/login.html"
class Logout(LogoutView):
    next_page = "/"
   
@method_decorator(csrf_protect)
def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

User = get_user_model()

class RegisterUser(FormView):
    template_name = "users/accounts/register.html"
    form_class = RegisterUserForm
    success_url = reverse_lazy("index")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        current_site = get_current_site(self.request)
        mail_subject = 'Activate your account'
        message = render_to_string("users/accounts/acc_activate_email.html", {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
            'protocol': 'https' if self.request.is_secure() else 'http',
        })

        email = EmailMessage(mail_subject, message, to=[user.email])
        email.content_subtype = "html"  # If you want to send HTML content
        email.send()

        messages.success(self.request, "Account created successfully. Please check your email to activate your account.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)

def profile(request):
    return render(request, 'users/accounts/profile.html')
def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()

        # VERY IMPORTANT! Specify backend explicitly:
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return render(request, 'users/accounts/activation_success.html')
    else:
        return render(request, 'users/accounts/activation_failed.html')
    


class ResendActivationEmailView(View):
    template_name = 'users/accounts/resend_activation.html'

    def get(self, request):
        form = ResendActivationEmailForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ResendActivationEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                if user.is_active:
                    messages.info(request, 'This account is already active.')
                else:
                    current_site = get_current_site(request)
                    mail_subject = 'Activate your account'
                    message = render_to_string('users/accounts/acc_activate_email.html', {
                        'user': user,
                        'domain': current_site.domain,
                        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                        'token': account_activation_token.make_token(user),
                    })
                    email_message = EmailMessage(mail_subject, message, to=[user.email])
                    email_message.send()
                    messages.success(request, 'A new activation link has been sent to your email.')
            except User.DoesNotExist:
                messages.error(request, 'No account found with that email.')
            return redirect('users:resend_activation')
        return render(request, self.template_name, {'form': form})
    
    
    
    
