from django import forms

from .models import Branch, BusinessSettings


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "code", "address", "phone", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "code": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "address": forms.Textarea(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "rows": 3}
            ),
            "phone": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "mt-3 h-4 w-4 rounded border-slate-300 text-slate-900"}),
        }


class BusinessSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tenant-scoped querysets declared in Meta are created before a request
        # establishes tenant context, so refresh this field queryset per request.
        self.fields["default_branch"].queryset = Branch.objects.filter(is_active=True).order_by("name")

    class Meta:
        model = BusinessSettings
        fields = [
            "business_name",
            "default_branch",
            "address",
            "phone",
            "receipt_footer",
            "vat_enabled",
            "vat_rate_percent",
            "loyalty_points_per_1000",
            "loyalty_cash_value_per_point",
            "thermal_paper_width",
        ]
        widgets = {
            "business_name": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "default_branch": forms.Select(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "address": forms.Textarea(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "rows": 3}
            ),
            "phone": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "receipt_footer": forms.TextInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "vat_enabled": forms.CheckboxInput(
                attrs={"class": "mt-3 h-4 w-4 rounded border-slate-300 text-slate-900"}
            ),
            "vat_rate_percent": forms.NumberInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "step": "0.01", "min": "0", "max": "100"}
            ),
            "loyalty_points_per_1000": forms.NumberInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
            "loyalty_cash_value_per_point": forms.NumberInput(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "step": "0.01"}
            ),
            "thermal_paper_width": forms.Select(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}
            ),
        }
