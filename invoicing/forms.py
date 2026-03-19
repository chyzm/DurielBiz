from decimal import Decimal

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.text import slugify

from accounts.forms import StyledPasswordChangeForm, StyledPasswordResetForm, StyledSetPasswordForm
from accounts.models import User

from .models import Document, DocumentItem, InvoiceBusiness, ServiceItem


def styled_widget(css_class="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900"):
    return {"class": css_class}


class ToolsSignupForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs=styled_widget()))
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs=styled_widget()))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs=styled_widget()))
    business_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs=styled_widget()))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("password1", "password2"):
            self.fields[field_name].widget.attrs.update(styled_widget())

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_business_name(self):
        business_name = self.cleaned_data["business_name"].strip()
        slug = slugify(business_name)
        if not slug:
            raise forms.ValidationError("Enter a valid business name.")
        if InvoiceBusiness.objects.filter(slug=slug).exists():
            raise forms.ValidationError("A tools workspace already exists for this business name.")
        return business_name

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = self.generate_username(email)
        user.role = User.Role.ADMIN
        if commit:
            user.save()
        return user

    @staticmethod
    def generate_username(email):
        base_username = slugify(email.split("@", 1)[0]) or "invoice-user"
        candidate = base_username
        suffix = 1
        while User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base_username}-{suffix}"
        return candidate


class ToolsAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs=styled_widget()))
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs=styled_widget()),
    )

    error_messages = {
        "invalid_login": "Please enter the correct invoicing email and password.",
        "inactive": "This account is inactive.",
    }

    def clean(self):
        email = self.cleaned_data.get("username", "").strip().lower()
        password = self.cleaned_data.get("password")
        if email and password:
            linked_user = User.objects.filter(email__iexact=email).first()
            username = linked_user.username if linked_user else email
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            if not hasattr(self.user_cache, "invoice_business"):
                raise forms.ValidationError("No invoicing workspace is linked to this email.", code="invalid_login")
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class InvoiceBusinessForm(forms.ModelForm):
    class Meta:
        model = InvoiceBusiness
        fields = ("name", "contact_email", "contact_phone", "address", "logo")
        widgets = {
            "name": forms.TextInput(attrs=styled_widget()),
            "contact_email": forms.EmailInput(attrs=styled_widget()),
            "contact_phone": forms.TextInput(attrs=styled_widget()),
            "address": forms.Textarea(attrs={**styled_widget(), "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["logo"].widget.attrs.update(styled_widget())
        self.fields["logo"].help_text = "PNG or JPG only. Maximum file size: 1 MB."


class ServiceItemForm(forms.ModelForm):
    class Meta:
        model = ServiceItem
        fields = ("name", "description", "unit_price", "is_active")
        widgets = {
            "name": forms.TextInput(attrs=styled_widget()),
            "description": forms.TextInput(attrs=styled_widget()),
            "unit_price": forms.NumberInput(attrs={**styled_widget(), "step": "0.01", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded border-slate-300 text-slate-900"}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = (
            "customer_name",
            "customer_email",
            "customer_phone",
            "issue_date",
            "due_date",
            "signature_mode",
            "signature_initials",
            "discount_amount",
            "notes",
        )
        widgets = {
            "customer_name": forms.TextInput(attrs=styled_widget()),
            "customer_email": forms.EmailInput(attrs=styled_widget()),
            "customer_phone": forms.TextInput(attrs=styled_widget()),
            "issue_date": forms.DateInput(attrs=styled_widget(), format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs=styled_widget(), format="%Y-%m-%d"),
            "signature_mode": forms.Select(attrs=styled_widget()),
            "signature_initials": forms.TextInput(attrs={**styled_widget(), "maxlength": "10", "placeholder": "e.g. DTA"}),
            "discount_amount": forms.NumberInput(attrs={**styled_widget(), "step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={**styled_widget(), "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["issue_date"].widget.input_type = "date"
        self.fields["due_date"].widget.input_type = "date"

    def clean_discount_amount(self):
        discount_amount = self.cleaned_data.get("discount_amount") or Decimal("0.00")
        if discount_amount < 0:
            raise forms.ValidationError("Discount cannot be negative.")
        return discount_amount

    def clean_signature_initials(self):
        initials = (self.cleaned_data.get("signature_initials") or "").strip().upper()
        if len(initials) > 10:
            raise forms.ValidationError("Initials must be 10 characters or fewer.")
        return initials


class DocumentItemForm(forms.ModelForm):
    class Meta:
        model = DocumentItem
        fields = ("service", "description", "quantity", "unit_price", "discount_amount")
        widgets = {
            "service": forms.Select(attrs=styled_widget()),
            "description": forms.TextInput(attrs=styled_widget()),
            "quantity": forms.NumberInput(attrs={**styled_widget(), "step": "0.01", "min": "0.01"}),
            "unit_price": forms.NumberInput(attrs={**styled_widget(), "step": "0.01", "min": "0"}),
            "discount_amount": forms.NumberInput(attrs={**styled_widget(), "step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].required = False
        self.fields["description"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_price"].required = False
        self.fields["discount_amount"].required = False
        if business is not None:
            self.fields["service"].queryset = business.services.filter(is_active=True).order_by("name")
        else:
            self.fields["service"].queryset = ServiceItem.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        description = (cleaned_data.get("description") or "").strip()
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")
        discount_amount = cleaned_data.get("discount_amount")
        has_any_data = bool(service or description or quantity is not None or unit_price is not None or discount_amount is not None)

        if not has_any_data:
            cleaned_data["description"] = ""
            return cleaned_data

        if service and not description:
            description = service.name
            cleaned_data["description"] = description
        if service:
            cleaned_data["unit_price"] = service.unit_price
            unit_price = service.unit_price
        if not description:
            raise forms.ValidationError("Enter a service description or select a saved service.")
        if quantity is None or quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        if unit_price is None or unit_price < 0:
            raise forms.ValidationError("Unit price cannot be negative.")
        if discount_amount is None:
            cleaned_data["discount_amount"] = Decimal("0.00")
            discount_amount = cleaned_data["discount_amount"]
        if discount_amount < 0:
            raise forms.ValidationError("Discount cannot be negative.")
        line_base = quantity * unit_price
        if discount_amount > line_base:
            raise forms.ValidationError("Item discount cannot be more than the line amount.")
        return cleaned_data


class DocumentItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, business=None, **kwargs):
        self.business = business
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.fields["service"].queryset = business.services.filter(is_active=True).order_by("name") if business else ServiceItem.objects.none()

    def clean(self):
        super().clean()
        active_forms = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            description = (form.cleaned_data.get("description") or "").strip()
            service = form.cleaned_data.get("service")
            quantity = form.cleaned_data.get("quantity")
            unit_price = form.cleaned_data.get("unit_price")
            discount_amount = form.cleaned_data.get("discount_amount")
            if service or description or quantity is not None or unit_price is not None or discount_amount is not None:
                active_forms += 1
        if active_forms == 0:
            raise forms.ValidationError("Add at least one invoice item.")


BaseDocumentItemFormSet = inlineformset_factory(
    Document,
    DocumentItem,
    form=DocumentItemForm,
    formset=DocumentItemFormSet,
    extra=1,
    can_delete=True,
)


PasswordResetForm = StyledPasswordResetForm
SetPasswordForm = StyledSetPasswordForm
PasswordChangeForm = StyledPasswordChangeForm
