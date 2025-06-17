from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import FormView
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from .models import  CustomUser
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import PasswordChangeForm

CustomUser = get_user_model()


class RegisterUserForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Username or Email')
    
    


User = get_user_model()





class ResendActivationEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
            "class": "w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"
        })
    )
    
    
    




class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'hidden',
                'id': 'avatar-upload',
                'accept': 'image/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add common classes to all fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring-blue-500 focus:border-blue-500'
            })

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style all password fields consistently
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'autocomplete': 'new-password'
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                # optionally resend activation email here
                raise ValidationError("You already have an account that needs activation. Check your email.")
        except User.DoesNotExist:
            pass
        return email
class RemoveHelpTextMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ''
class OptionalFieldsMixin:
    """
    Mixin to make all fields optional automatically.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter your username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter your email'
            }),
        }



