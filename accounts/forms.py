from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm, UserCreationForm
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


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, is_cloud_login=False, **kwargs):
        self.is_cloud_login = is_cloud_login
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email" if is_cloud_login else "Username"
        self.fields["username"].widget.attrs["class"] = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
        self.fields["password"].widget.attrs["class"] = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
        if is_cloud_login:
            self.fields["username"].widget.attrs["placeholder"] = "you@company.com"
        else:
            self.fields["username"].widget.attrs["placeholder"] = "Username"

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if self.is_cloud_login and username and password:
            linked_user = User.objects.filter(email__iexact=username).first()
            normalized_username = linked_user.username if linked_user else username
            self.user_cache = authenticate(self.request, username=normalized_username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
            self.cleaned_data["username"] = normalized_username
            return self.cleaned_data

        return super().clean()


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
