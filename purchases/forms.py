from django import forms
from django.utils import timezone

from accounts.permissions import active_branches_for_user, get_user_branch, is_admin_user
from reports.models import Branch, BusinessSettings
from suppliers.models import Supplier
from products.models import Product


class PurchaseReceiveForm(forms.Form):
    def __init__(self, *args, purchase=None, user=None, **kwargs):
        self.purchase = purchase
        super().__init__(*args, **kwargs)
        branch_queryset = active_branches_for_user(user) if user else Branch.objects.filter(is_active=True).order_by("name")
        user_branch = get_user_branch(user) if user else None
        self.fields["branch"].queryset = branch_queryset
        if user_branch and not is_admin_user(user):
            self.fields["branch"].disabled = True
            self.fields["product"].queryset = Product.objects.filter(branch_stocks__branch=user_branch).order_by("name").distinct()
        if not self.is_bound and "initial" not in kwargs:
            self.fields["received_at"].initial = timezone.now().strftime("%Y-%m-%dT%H:%M")
            self.fields["branch"].initial = user_branch or BusinessSettings.get_solo().default_branch

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.order_by("name"),
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    invoice_no = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    received_at = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(
            attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "type": "datetime-local"}
        ),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by("name"),
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    cost_price = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "step": "0.01"}),
    )
    expiry_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "type": "date"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "rows": 3}),
    )

    def clean_invoice_no(self):
        return self.cleaned_data["invoice_no"].strip()
