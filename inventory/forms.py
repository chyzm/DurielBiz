from django import forms

from accounts.permissions import active_branches_for_user, get_user_branch, is_admin_user
from reports.models import Branch, BusinessSettings

from .models import InventoryLog
from products.models import Product


class InventoryAdjustmentForm(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        branch_queryset = active_branches_for_user(user) if user else Branch.objects.filter(is_active=True).order_by("name")
        user_branch = get_user_branch(user) if user else None
        self.fields["branch"].queryset = branch_queryset
        # Build this queryset during the request, after tenant middleware has set
        # the active business. A class-level queryset is evaluated without that
        # context and can stay empty for the lifetime of the worker process.
        self.fields["product"].queryset = Product.objects.order_by("name")
        if user_branch and not is_admin_user(user):
            self.fields["branch"].disabled = True
        if not self.is_bound and "branch" not in self.initial:
            self.fields["branch"].initial = user_branch or BusinessSettings.get_solo().default_branch

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by("name"),
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    action = forms.ChoiceField(
        choices=InventoryLog.Action.choices,
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
        help_text="For adjust, enter the final stock level.",
    )
    reason = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    reference = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
