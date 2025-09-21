from django import forms

from .models import Order


class OrderForm(forms.ModelForm):
    PAYMENT_CHOICES = [
        ("card", "Card"),
        ("mpesa", "M-Pesa"),
        ("paypal", "PayPal"),
    ]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(
            attrs={
                "class": "mr-2 text-blue-600 focus:ring-blue-500",
            }
        ),
        label="Select Payment Method",
    )

    class Meta:
        model = Order
        fields = [
            "full_name",
            "email",
            "address",
            # "latitude",     # hidden
            # "longitude",    # hidden
            "payment_method",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "Enter your full name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "Enter your email",
                }
            ),
            "address": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md",
                    "placeholder": "Enter your address",
                }
            ),
            # 'latitude': forms.HiddenInput(),
            # 'longitude': forms.HiddenInput(),
        }
