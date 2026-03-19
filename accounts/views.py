import os
from functools import wraps

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator

from pos_system.pagination import paginate_queryset

from cloudsync.services import user_business
from .activity import log_activity
from .forms import (
    EmailOrUsernameAuthenticationForm,
    StaffUserCreationForm,
    StaffUserUpdateForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .permissions import get_role_home_url, role_required
from accounts.models import ActivityLog, User
from inventory.models import InventoryLog
from purchases.models import Purchase
from sales.models import Sale
from cloudsync.models import Business as CloudBusiness, SyncEvent
from invoicing.models import Document, InvoiceBusiness, ToolSubscription


def is_cloud_request(request):
    if os.getenv("DURIELBIZ_DESKTOP") == "1":
        return False
    host = request.get_host().split(":")[0].lower()
    if host in {"127.0.0.1", "localhost"}:
        return False
    return True


class CloudModeRequiredMixin:
    fallback_url = reverse_lazy("accounts:login")
    fallback_message = "This account action is available only on the cloud dashboard."

    def dispatch(self, request, *args, **kwargs):
        if not is_cloud_request(request):
            messages.info(request, self.fallback_message)
            return redirect(self.fallback_url)
        return super().dispatch(request, *args, **kwargs)


def superadmin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Only the superadmin can access that page.")
            return redirect(get_role_home_url(request.user))
        return view_func(request, *args, **kwargs)

    return _wrapped


class AccountLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_form_class(self):
        view = self

        class BoundAuthenticationForm(EmailOrUsernameAuthenticationForm):
            def __init__(self, *args, **kwargs):
                kwargs["is_cloud_login"] = is_cloud_request(view.request)
                super().__init__(*args, **kwargs)

        return BoundAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_cloud_login"] = is_cloud_request(self.request)
        return context


class CloudPasswordResetView(CloudModeRequiredMixin, auth_views.PasswordResetView):
    form_class = StyledPasswordResetForm
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password-reset-done")


class CloudPasswordResetDoneView(CloudModeRequiredMixin, auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class CloudPasswordResetConfirmView(CloudModeRequiredMixin, auth_views.PasswordResetConfirmView):
    form_class = StyledSetPasswordForm
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password-reset-complete")


class CloudPasswordResetCompleteView(CloudModeRequiredMixin, auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


class CloudPasswordChangeView(CloudModeRequiredMixin, auth_views.PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("accounts:password-change-done")
    fallback_url = reverse_lazy("accounts:home")
    fallback_message = "Password change is not available from the local desktop app."


class CloudPasswordChangeDoneView(CloudModeRequiredMixin, auth_views.PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"
    fallback_url = reverse_lazy("accounts:home")
    fallback_message = "Password change is not available from the local desktop app."


@login_required
def role_home(request):
    return redirect(get_role_home_url(request.user))


@login_required
@role_required(User.Role.ADMIN)
def admin_center(request):
    users_page = paginate_queryset(request, User.objects.order_by("username"), per_page=10, page_param="users_page")
    context = {
        "staff_count": User.objects.filter(is_staff=True).count(),
        "cashier_count": User.objects.filter(role=User.Role.CASHIER).count(),
        "recent_sales_count": Sale.objects.filter(status=Sale.Status.COMPLETED).count(),
        "recent_purchase_count": Purchase.objects.count(),
        "inventory_event_count": InventoryLog.objects.count(),
        "users": users_page,
        "activity_count": ActivityLog.objects.count(),
        "users_page_obj": users_page,
    }
    return render(request, "accounts/admin_center.html", context)


@superadmin_required
def service_admin_dashboard(request):
    tab = request.GET.get("tab", "tools").strip().lower()
    if tab not in {"tools", "cloud"}:
        tab = "tools"

    subscriptions = (
        ToolSubscription.objects.select_related("business", "business__owner")
        .annotate(document_count=Count("business__documents"), service_count=Count("business__services"))
        .order_by("expires_at", "business__name")
    )
    for subscription in subscriptions:
        subscription.refresh_status()

    cloud_businesses = (
        CloudBusiness.objects.select_related("owner", "sync_credential")
        .annotate(
            branch_count=Count("branches", distinct=True),
            sale_count=Count("sales", distinct=True),
            purchase_count=Count("purchases", distinct=True),
        )
        .order_by("name")
    )
    cloud_business_rows = [
        {
            "business": business,
            "last_synced_at": getattr(getattr(business, "sync_credential", None), "last_synced_at", None),
        }
        for business in cloud_businesses
    ]

    context = {
        "active_tab": tab,
        "tool_metrics": {
            "total_businesses": InvoiceBusiness.objects.count(),
            "trial_count": subscriptions.filter(status=ToolSubscription.Status.TRIAL).count(),
            "active_count": subscriptions.filter(status=ToolSubscription.Status.ACTIVE).count(),
            "expired_count": subscriptions.filter(status=ToolSubscription.Status.EXPIRED).count(),
        },
        "tools_subscriptions": subscriptions,
        "recent_documents": Document.objects.select_related("business").order_by("-created_at")[:10],
        "cloud_metrics": {
            "business_count": cloud_businesses.count(),
            "sync_event_count": SyncEvent.objects.count(),
            "active_token_count": CloudBusiness.objects.filter(sync_credential__is_active=True).count(),
        },
        "cloud_businesses": cloud_business_rows,
        "recent_sync_events": SyncEvent.objects.select_related("business").order_by("-created_at")[:12],
    }
    return render(request, "accounts/service_admin.html", context)


@superadmin_required
def activate_tools_subscription(request, pk):
    if request.method != "POST":
        return redirect("accounts:service-admin")
    subscription = get_object_or_404(ToolSubscription.objects.select_related("business"), pk=pk)
    subscription.activate_paid_cycle()
    log_activity(
        user=request.user,
        module=ActivityLog.Module.SETTINGS,
        action="tools_subscription_activated",
        description=f"{request.user.username} activated a 30-day Tools subscription for {subscription.business.name}",
        entity_type="tool_subscription",
        entity_id=subscription.pk,
        metadata={"business": subscription.business.name, "expires_at": subscription.expires_at.isoformat()},
    )
    messages.success(request, f"30-day paid cycle activated for {subscription.business.name}.")
    return redirect(f"{reverse_lazy('accounts:service-admin')}?tab=tools")


@login_required
@role_required(User.Role.ADMIN)
def user_management(request):
    form = StaffUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.USERS,
            action="user_created",
            description=f"{request.user.username} created user {user.username}",
            entity_type="user",
            entity_id=user.pk,
        )
        messages.success(request, f"User {user.username} created successfully.")
        return redirect("accounts:user-management")

    context = {
        "form": form,
        "users": paginate_queryset(request, User.objects.order_by("username"), per_page=10),
    }
    return render(request, "accounts/user_management.html", context)


@login_required
@role_required(User.Role.ADMIN)
def user_detail(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    return render(request, "accounts/user_detail.html", {"user_obj": user_obj})


@login_required
@role_required(User.Role.ADMIN)
def user_update(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    form = StaffUserUpdateForm(request.POST or None, instance=user_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.USERS,
            action="user_updated",
            description=f"{request.user.username} updated user {user_obj.username}",
            entity_type="user",
            entity_id=user_obj.pk,
        )
        messages.success(request, f"User {user_obj.username} updated successfully.")
        return redirect("accounts:user-detail", pk=user_obj.pk)
    return render(request, "accounts/user_form.html", {"form": form, "user_obj": user_obj})


@login_required
@role_required(User.Role.ADMIN)
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        username = user_obj.username
        try:
            user_obj.delete()
            log_activity(
                user=request.user,
                module=ActivityLog.Module.USERS,
                action="user_deleted",
                description=f"{request.user.username} deleted user {username}",
                entity_type="user",
                entity_id=pk,
            )
            messages.success(request, f"User {username} deleted successfully.")
        except ProtectedError:
            user_obj.is_active = False
            user_obj.save(update_fields=["is_active"])
            log_activity(
                user=request.user,
                module=ActivityLog.Module.USERS,
                action="user_deactivated",
                description=f"{request.user.username} deactivated user {username}",
                entity_type="user",
                entity_id=user_obj.pk,
            )
            messages.warning(request, f"User {username} has related records and was deactivated instead.")
        return redirect("accounts:user-management")
    return render(request, "accounts/user_confirm_delete.html", {"user_obj": user_obj})


@login_required
@role_required(User.Role.ADMIN)
def activity_log_list(request):
    module = request.GET.get("module", "").strip()
    logs = ActivityLog.objects.select_related("user").order_by("-created_at")
    if module:
        logs = logs.filter(module=module)
    logs_page = paginate_queryset(request, logs, per_page=20)
    return render(
        request,
        "accounts/activity_log.html",
        {"logs": logs_page, "modules": ActivityLog.Module.choices, "selected_module": module},
    )


@login_required
def about_support(request):
    business = user_business(request.user)
    return render(
        request,
        "accounts/about_support.html",
        {
            "base_template": "cloudsync/base.html" if business else "base.html",
            "support_phone": "07031016787",
            "support_email": "info@durieltech.com.ng",
            "company_name": "DurielTech",
            "product_name": "DurielBiz POS",
            "app_version": "1.0.0",
            "deployment_modes": [
                "Local desktop POS with offline-first operation",
                "LAN access on the same network",
                "Cloud dashboard sync for remote monitoring",
            ],
            "license_notes": [
                "Release builds should be distributed with the approved installer or the packaged desktop binaries.",
                "Cloud dashboard access depends on valid business account setup and sync configuration.",
                "Windows publisher verification requires a real code-signing certificate during release builds.",
            ],
        },
    )
