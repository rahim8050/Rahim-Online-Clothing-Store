from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

User = get_user_model()  # Use consistently everywhere


# =======================
# Register Form
# =======================
class RegisterUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "your-class"}),
            "email": forms.EmailInput(attrs={"class": "your-class"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["password1", "password2"]:
            self.fields[field_name].widget.attrs.update({"class": "your-class"})


# =======================
# Login Form
# =======================
class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or Username",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Email or Username",
                "autocomplete": "username",
                "autofocus": "autofocus",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "autocomplete": "current-password",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10",
            }
        ),
    )


# =======================
# Resend Activation
# =======================
class ResendActivationEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "you@example.com",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm",
            }
        ),
    )


# =======================
# User Profile Update
# =======================
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "avatar"]
        widgets = {
            "avatar": forms.FileInput(
                attrs={"class": "hidden", "id": "avatar-upload", "accept": "image/*"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                {
                    "class": "w-full px-4 py-2 border rounded-lg focus:ring-blue-500 focus:border-blue-500"
                }
            )


# =======================
# Password Reset Form
# =======================
class CustomPasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "class": "w-full mt-1 p-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500",
                "placeholder": "you@example.com",
            }
        ),
    )


# =======================
# Password Change Form
# =======================
class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                {
                    "class": "w-full px-4 py-2 border rounded-lg focus:ring-blue-500 focus:border-blue-500",
                    "autocomplete": "new-password",
                }
            )


# =======================
# Mixins
# =======================
class RemoveHelpTextMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""


class OptionalFieldsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


# =======================
# Profile Form
# =======================
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter your username",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter your email",
                }
            ),
        }
