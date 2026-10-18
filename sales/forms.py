import json
from decimal import Decimal

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
    cash_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, required=False, initial=Decimal("0.00"), widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2", "step": "0.01"}))
    card_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, required=False, initial=Decimal("0.00"), widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2", "step": "0.01"}))
    transfer_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, required=False, initial=Decimal("0.00"), widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2", "step": "0.01"}))
    redeemed_points = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm", "placeholder": "0"}
        ),
    )
    discount = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(
            attrs={"class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm", "placeholder": "0.00"}
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
        if not isinstance(items, list) or not items:
            raise ValidationError("Add at least one product to the cart.")
        if len(items) > 100:
            raise ValidationError("A sale cannot contain more than 100 cart lines.")
        seen_products = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError("Cart items are invalid.")
            try:
                product_id = int(item.get("product_id"))
                quantity = int(item.get("quantity", 0))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValidationError("Cart items are invalid.") from exc
            if (
                product_id <= 0
                or str(product_id) != str(item.get("product_id"))
                or quantity <= 0
                or str(quantity) != str(item.get("quantity"))
            ):
                raise ValidationError("Cart quantities must be greater than zero.")
            if product_id in seen_products:
                raise ValidationError("Each product may only appear once in the cart.")
            seen_products.add(product_id)
            # Never accept an amount supplied by the browser as an authoritative price.
            item.pop("unit_price", None)
        return items

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("payment_method") == Sale.PaymentMethod.MIXED:
            splits = [cleaned.get("cash_amount") or Decimal("0"),
                      cleaned.get("card_amount") or Decimal("0"),
                      cleaned.get("transfer_amount") or Decimal("0")]
            if sum(amount > 0 for amount in splits) < 2:
                self.add_error("payment_method", "Mixed payment needs at least two non-zero tender amounts.")
            elif sum(splits) != cleaned.get("paid_amount"):
                self.add_error("paid_amount", "Paid amount must equal the total of the cash, card, and transfer amounts.")
        return cleaned

    def payment_tenders(self):
        if self.cleaned_data.get("payment_method") != Sale.PaymentMethod.MIXED:
            return None
        return [
            {"payment_method": method, "tendered_amount": self.cleaned_data[field]}
            for field, method in (("cash_amount", Sale.PaymentMethod.CASH),
                                  ("card_amount", Sale.PaymentMethod.CARD),
                                  ("transfer_amount", Sale.PaymentMethod.TRANSFER))
            if self.cleaned_data.get(field)
        ]
