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
    success_url = reverse_lazy("index")  # Use a named URL if possible

    def form_valid(self, form):
        try:
            user = form.save(commit=False)
            user.is_active = False  # Require email activation
            user.save()

            current_site = get_current_site(self.request)
            mail_subject = 'Activate your account'
            message = render_to_string("users/accounts/acc_activate_email.html", {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })

            email = EmailMessage(mail_subject, message, to=[user.email])
            email.send()

            messages.success(self.request, "Account created successfully.")
            messages.success(self.request, "Please check your email to activate your account.")
            return redirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f"An error occurred: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        # Collect and display all form errors via messages
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    messages.error(self.request, f"{form.fields[field].label}: {error}")
        return super().form_invalid(form)

    



def profile(request):
    return render(request, 'users/accounts/profile.html')





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
    
    
    
