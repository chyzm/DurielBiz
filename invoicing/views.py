from functools import wraps

import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views.generic import FormView

from accounts.views import is_cloud_request

from .forms import (
    BaseDocumentItemFormSet,
    DocumentForm,
    InvoiceBusinessForm,
    PasswordChangeForm,
    PasswordResetForm,
    ServiceItemForm,
    SetPasswordForm,
    ToolsAuthenticationForm,
    ToolsSignupForm,
)
from .models import Document, InvoiceBusiness, ServiceItem
from .services import create_initial_subscription, render_document_pdf


def is_local_dev_request(request):
    host = request.get_host().split(":", 1)[0].lower()
    return host in {"127.0.0.1", "localhost"} and os.getenv("DURIELBIZ_DESKTOP") != "1"


def is_tools_request_allowed(request):
    return is_cloud_request(request) or settings.INVOICING_ALLOW_LOCAL or is_local_dev_request(request)


def cloud_tools_redirect(request):
    target_url = f"{settings.DURIELBIZ_SITE_URL.rstrip('/')}{request.get_full_path()}"
    return redirect(target_url)


def cloud_only_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_tools_request_allowed(request):
            return cloud_tools_redirect(request)
        return view_func(request, *args, **kwargs)

    return wrapped


def invoice_business_for_user(user):
    return getattr(user, "invoice_business", None)


def tool_login_required(view_func):
    @wraps(view_func)
    @login_required(login_url=reverse_lazy("invoicing:login"))
    def wrapped(request, *args, **kwargs):
        if not is_tools_request_allowed(request):
            return cloud_tools_redirect(request)
        business = invoice_business_for_user(request.user)
        if business is None:
            messages.error(request, "No invoicing workspace is linked to this account.")
            return redirect("invoicing:home")
        request.invoice_business = business
        return view_func(request, *args, **kwargs)

    return wrapped


def active_subscription_required(view_func):
    @wraps(view_func)
    @tool_login_required
    def wrapped(request, *args, **kwargs):
        if not request.invoice_business.has_active_subscription():
            subscription = request.invoice_business.subscription
            if subscription and subscription.has_paid_access:
                messages.error(request, "Your paid cycle has expired. Renew to continue using the invoice service.")
            else:
                messages.error(request, "Your 48-hour free trial has expired. Upgrade to the paid version to continue.")
            return redirect("invoicing:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapped


class CloudOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        if not is_tools_request_allowed(request):
            return cloud_tools_redirect(request)
        return super().dispatch(request, *args, **kwargs)


class ToolsLoginView(CloudOnlyMixin, auth_views.LoginView):
    template_name = "invoicing/login.html"
    authentication_form = ToolsAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("invoicing:dashboard")


class ToolsSignupView(CloudOnlyMixin, FormView):
    template_name = "invoicing/signup.html"
    form_class = ToolsSignupForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and invoice_business_for_user(request.user):
            return redirect("invoicing:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save()
            business_name = form.cleaned_data["business_name"]
            business = InvoiceBusiness.objects.create(
                owner=user,
                name=business_name,
                slug=slugify(business_name),
                contact_email=form.cleaned_data["email"],
            )
            create_initial_subscription(business)
        auth_login(self.request, user)
        messages.success(self.request, "Your invoicing workspace is ready.")
        return redirect("invoicing:dashboard")


class ToolsPasswordResetView(CloudOnlyMixin, auth_views.PasswordResetView):
    form_class = PasswordResetForm
    template_name = "invoicing/password_reset_form.html"
    email_template_name = "invoicing/password_reset_email.txt"
    subject_template_name = "invoicing/password_reset_subject.txt"
    success_url = reverse_lazy("invoicing:password-reset-done")


class ToolsPasswordResetDoneView(CloudOnlyMixin, auth_views.PasswordResetDoneView):
    template_name = "invoicing/password_reset_done.html"


class ToolsPasswordResetConfirmView(CloudOnlyMixin, auth_views.PasswordResetConfirmView):
    form_class = SetPasswordForm
    template_name = "invoicing/password_reset_confirm.html"
    success_url = reverse_lazy("invoicing:password-reset-complete")


class ToolsPasswordResetCompleteView(CloudOnlyMixin, auth_views.PasswordResetCompleteView):
    template_name = "invoicing/password_reset_complete.html"


class ToolsPasswordChangeView(CloudOnlyMixin, auth_views.PasswordChangeView):
    form_class = PasswordChangeForm
    template_name = "invoicing/password_change_form.html"
    success_url = reverse_lazy("invoicing:dashboard")


@cloud_only_required
def tools_home(request):
    if request.user.is_authenticated and invoice_business_for_user(request.user):
        return redirect("invoicing:dashboard")
    return render(request, "invoicing/tools_home.html")


@tool_login_required
def dashboard(request):
    business = request.invoice_business
    subscription = business.subscription
    if subscription:
        subscription.refresh_status()
    recent_documents = business.documents.prefetch_related("items").order_by("-created_at")[:6]
    return render(
        request,
        "invoicing/dashboard.html",
        {
            "business": business,
            "subscription": subscription,
            "recent_documents": recent_documents,
        },
    )


@tool_login_required
def business_settings(request):
    business = request.invoice_business
    form = InvoiceBusinessForm(request.POST or None, request.FILES or None, instance=business)
    if request.method == "POST" and form.is_valid():
        candidate_slug = slugify(form.cleaned_data["name"])
        if InvoiceBusiness.objects.exclude(pk=business.pk).filter(slug=candidate_slug).exists():
            form.add_error("name", "That business name is already in use.")
        else:
            updated_business = form.save(commit=False)
            updated_business.slug = candidate_slug
            updated_business.save()
            messages.success(request, "Business profile updated.")
            return redirect("invoicing:business-settings")
    return render(request, "invoicing/business_form.html", {"business": business, "form": form})


@active_subscription_required
def service_list(request):
    business = request.invoice_business
    services = business.services.order_by("name")
    return render(request, "invoicing/service_list.html", {"business": business, "services": services})


@active_subscription_required
def service_create(request):
    business = request.invoice_business
    form = ServiceItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.business = business
        service.save()
        messages.success(request, "Service saved.")
        return redirect("invoicing:service-list")
    return render(request, "invoicing/service_form.html", {"business": business, "form": form, "page_title": "Add Service"})


@active_subscription_required
def service_update(request, pk):
    business = request.invoice_business
    service = get_object_or_404(ServiceItem, pk=pk, business=business)
    form = ServiceItemForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service updated.")
        return redirect("invoicing:service-list")
    return render(
        request,
        "invoicing/service_form.html",
        {"business": business, "form": form, "page_title": "Edit Service", "service": service},
    )


@active_subscription_required
def service_delete(request, pk):
    business = request.invoice_business
    service = get_object_or_404(ServiceItem, pk=pk, business=business)
    if request.method == "POST":
        service.delete()
        messages.success(request, "Service deleted.")
        return redirect("invoicing:service-list")
    return render(request, "invoicing/service_confirm_delete.html", {"business": business, "service": service})


@active_subscription_required
def document_list(request):
    business = request.invoice_business
    doc_type = request.GET.get("type", "").strip()
    documents = business.documents.prefetch_related("items").order_by("-created_at")
    if doc_type in {Document.DocumentType.INVOICE, Document.DocumentType.RECEIPT}:
        documents = documents.filter(document_type=doc_type)
    return render(
        request,
        "invoicing/document_list.html",
        {
            "business": business,
            "documents": documents[:100],
            "selected_type": doc_type,
        },
    )


def build_document_formset(request, business, instance):
    kwargs = {"instance": instance, "prefix": "items", "business": business, "form_kwargs": {"business": business}}
    if request.method == "POST":
        kwargs["data"] = request.POST
    return BaseDocumentItemFormSet(**kwargs)


def persist_document_items(formset, document):
    kept_items = []
    position = 1
    for form in formset.forms:
        if not hasattr(form, "cleaned_data"):
            continue
        if form.cleaned_data.get("DELETE"):
            if form.instance.pk:
                form.instance.delete()
            continue
        description = (form.cleaned_data.get("description") or "").strip()
        service = form.cleaned_data.get("service")
        quantity = form.cleaned_data.get("quantity")
        unit_price = form.cleaned_data.get("unit_price")
        discount_amount = form.cleaned_data.get("discount_amount")
        if not (service or description or quantity is not None or unit_price is not None or discount_amount is not None):
            if form.instance.pk:
                form.instance.delete()
            continue
        item = form.save(commit=False)
        item.document = document
        item.position = position
        if item.service and not item.description:
            item.description = item.service.name
        item.save()
        kept_items.append(item.pk)
        position += 1

    document.items.exclude(pk__in=kept_items).delete()
    document.recalculate_totals()


@active_subscription_required
def document_create(request, document_type):
    business = request.invoice_business
    if document_type not in {Document.DocumentType.INVOICE, Document.DocumentType.RECEIPT}:
        raise Http404

    document = Document(business=business, created_by=request.user, document_type=document_type)
    form = DocumentForm(request.POST or None, instance=document)
    formset = build_document_formset(request, business, instance=document)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            document = form.save(commit=False)
            document.business = business
            document.created_by = request.user
            document.document_type = document_type
            document.save()
            persist_document_items(formset, document)
        messages.success(request, f"{document.get_document_type_display()} created successfully.")
        return redirect("invoicing:document-detail", pk=document.pk)

    return render(
        request,
        "invoicing/document_form.html",
        {
            "business": business,
            "form": form,
            "formset": formset,
            "document_type": document_type,
            "service_catalog": list(business.services.filter(is_active=True).values("id", "name", "unit_price")),
        },
    )


@active_subscription_required
def document_update(request, pk):
    business = request.invoice_business
    document = get_object_or_404(Document, pk=pk, business=business)
    form = DocumentForm(request.POST or None, instance=document)
    formset = build_document_formset(request, business, instance=document)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            persist_document_items(formset, document)
        messages.success(request, f"{document.get_document_type_display()} updated.")
        return redirect("invoicing:document-detail", pk=document.pk)

    return render(
        request,
        "invoicing/document_form.html",
        {
            "business": business,
            "form": form,
            "formset": formset,
            "document": document,
            "document_type": document.document_type,
            "service_catalog": list(business.services.filter(is_active=True).values("id", "name", "unit_price")),
        },
    )


@active_subscription_required
def document_detail(request, pk):
    business = request.invoice_business
    document = get_object_or_404(Document.objects.prefetch_related("items"), pk=pk, business=business)
    document.recalculate_totals()
    return render(request, "invoicing/document_detail.html", {"business": business, "document": document})


@active_subscription_required
def document_pdf(request, pk):
    business = request.invoice_business
    document = get_object_or_404(Document.objects.prefetch_related("items"), pk=pk, business=business)
    document.recalculate_totals()
    pdf_bytes = render_document_pdf(document)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{document.number}.pdf"'
    return response
