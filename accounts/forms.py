from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from .models import User
from reports.models import Branch

INPUT_CLASS = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"


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
        self.fields["username"].widget.attrs["class"] = "mt-1 w-full rounded-lg border border-slate-300 px-4 py-2.5"
        self.fields["password"].widget.attrs["class"] = "mt-1 w-full rounded-lg border border-slate-300 px-4 py-2.5"
        if is_cloud_login:
            self.fields["username"].widget.attrs["placeholder"] = "you@company.com"
            self.error_messages["invalid_login"] = "Please enter a correct email and password. Note that both fields may be case-sensitive."
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


class OTPRequestForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@company.com"})
    )


class OTPPasswordResetForm(forms.Form):
    code = forms.CharField(
        label="Verification code",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "6-digit code", "inputmode": "numeric", "autocomplete": "one-time-code"}),
    )
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}))
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}))

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Enter the 6-digit code exactly as emailed to you.")
        return code

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        if password1:
            password_validation.validate_password(password1, self.user)
        return password2


class CreateCloudBusinessForm(forms.Form):
    business_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    business_slug = forms.SlugField(
        max_length=80,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS}),
    )

    def clean_business_slug(self):
        from cloudsync.models import Business

        slug = self.cleaned_data["business_slug"].strip().lower()
        if Business.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This business slug is already in use.")
        return slug

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
