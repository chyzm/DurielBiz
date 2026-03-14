from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import User

from .models import Business


class CloudSignupForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    business_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )
    business_slug = forms.SlugField(
        max_length=80,
        widget=forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        widgets = {
            "username": forms.TextInput(attrs={"class": "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm")

    def clean_business_slug(self):
        slug = self.cleaned_data["business_slug"].strip().lower()
        if Business.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This business slug is already in use.")
        return slug
