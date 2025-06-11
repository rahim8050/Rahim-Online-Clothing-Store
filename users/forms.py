from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import FormView
from django.contrib.auth.forms import AuthenticationForm
from django import forms

from .models import  CustomUser

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class RegisterUserForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')
class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Username or Email')
