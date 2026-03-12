from django import forms

from .models import Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "phone", "email", "address", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "phone": forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "email": forms.EmailInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
            "address": forms.Textarea(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "rows": 3}
            ),
            "notes": forms.Textarea(
                attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm", "rows": 4}
            ),
        }
