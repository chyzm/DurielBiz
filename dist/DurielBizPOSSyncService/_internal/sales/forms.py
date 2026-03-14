import json

from django import forms
from django.core.exceptions import ValidationError

from .models import Customer, Sale


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "loyalty_points", "preferred_redeem_points"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "loyalty_points": forms.NumberInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "preferred_redeem_points": forms.NumberInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
        }


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm", "placeholder": "Customer name"}
        ),
    )
    customer_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm", "placeholder": "Customer phone"}
        ),
    )
    payment_method = forms.ChoiceField(
        choices=Sale.PaymentMethod.choices,
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"}),
    )
    paid_amount = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(
            attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm", "placeholder": "0.00"}
        ),
    )
    redeemed_points = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm", "placeholder": "0"}
        ),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm",
                "rows": 3,
                "placeholder": "Optional note",
            }
        ),
    )
    lane_name = forms.CharField(widget=forms.HiddenInput(), required=False)
    items_json = forms.CharField(widget=forms.HiddenInput())

    def clean_items_json(self):
        value = self.cleaned_data["items_json"]
        try:
            items = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError("Cart payload is invalid.") from exc
        if not items:
            raise ValidationError("Add at least one product to the cart.")
        for item in items:
            if int(item.get("quantity", 0)) <= 0:
                raise ValidationError("Cart quantities must be greater than zero.")
        return items
