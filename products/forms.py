from django import forms

from accounts.permissions import active_branches_for_user, get_user_branch, is_admin_user
from reports.models import Branch, BusinessSettings
from .models import Category, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "description": forms.Textarea(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "rows": 4}
            ),
        }


class ProductForm(forms.ModelForm):
    opening_stock = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
        help_text="Optional opening stock to add immediately after creating the product.",
    )
    opening_branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
        help_text="Branch to receive the opening stock. Defaults to the business default branch.",
    )

    def __init__(
        self,
        *args,
        include_opening_fields=True,
        include_branch_field=None,
        user=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.include_opening_fields = include_opening_fields
        if include_branch_field is None:
            include_branch_field = include_opening_fields
        branch_queryset = active_branches_for_user(user) if user else Branch.objects.filter(is_active=True).order_by("name")
        user_branch = get_user_branch(user) if user else None
        existing_branch = None
        if self.instance.pk:
            existing_branch = self.instance.branch_stocks.select_related("branch").order_by("branch__name").first()
        if include_branch_field and not self.is_bound:
            self.fields["opening_branch"].queryset = branch_queryset
            self.fields["opening_branch"].initial = (
                user_branch
                or (existing_branch.branch if existing_branch else None)
                or BusinessSettings.get_solo().default_branch
            )
        elif include_branch_field:
            self.fields["opening_branch"].queryset = branch_queryset
        if include_branch_field and user_branch and not is_admin_user(user):
            self.fields["opening_branch"].disabled = True
        if include_branch_field and not include_opening_fields:
            self.fields["opening_branch"].label = "Branch"
            self.fields["opening_branch"].help_text = "Choose the branch this product should be available under."
        if not include_opening_fields:
            self.fields.pop("opening_stock", None)
        if not include_branch_field:
            self.fields.pop("opening_branch", None)

    class Meta:
        model = Product
        fields = [
            "name",
            "barcode",
            "category",
            "supplier",
            "cost_price",
            "selling_price",
            "reorder_level",
            "expiry_date",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "barcode": forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "category": forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "supplier": forms.Select(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "cost_price": forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "step": "0.01"}),
            "selling_price": forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "step": "0.01"}),
            "reorder_level": forms.NumberInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "expiry_date": forms.DateInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-slate-300"}),
        }
