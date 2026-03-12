from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User
from reports.models import Branch


class StaffUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True).order_by("name")
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number", "role", "branch")

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        branch = cleaned_data.get("branch")
        if role != User.Role.ADMIN and branch is None:
            self.add_error("branch", "Assign a branch to this user.")
        return cleaned_data


class StaffUserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "role", "branch", "is_active", "is_staff")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True).order_by("name")
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        branch = cleaned_data.get("branch")
        if role != User.Role.ADMIN and branch is None:
            self.add_error("branch", "Assign a branch to this user.")
        return cleaned_data
