from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.views.generic import FormView

from users.forms import RegisterUserForm


# Create your views here.
def home (request):
    pass
class Login(LoginView):
    template_name = "users/accounts/login.html"

class RegisterUser(FormView):
    template_name = "users/accounts/register.html"
    form_class = RegisterUserForm
    success_url = "/"

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)