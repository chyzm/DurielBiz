import os
import logging
import secrets
from functools import wraps
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

from pos_system.pagination import paginate_queryset
from pos_system.throttle import register_attempt, throttle, too_many_attempts

from cloudsync.services import user_business
from .activity import get_client_ip, log_activity
from .forms import (
    CreateCloudBusinessForm,
    EmailOrUsernameAuthenticationForm,
    OTPPasswordResetForm,
    OTPRequestForm,
    StaffUserCreationForm,
    StaffUserUpdateForm,
    StyledPasswordChangeForm,
    StyledSetPasswordForm,
)
from .otp import consume_otp, create_otp, find_valid_otp, send_otp_email
from .permissions import get_role_home_url, role_required
from accounts.models import ActivityLog, EmailOTP, User
from inventory.models import InventoryLog
from purchases.models import Purchase
from sales.models import Sale
from cloudsync.models import Business as CloudBusiness, BusinessMembership, SyncCredential, SyncEvent
from invoicing.models import Document, InvoiceBusiness, ToolSubscription

logger = logging.getLogger(__name__)


def is_local_preview_eligible(request):
    """True only for a manual local run (never the packaged desktop app, which
    always sets DURIELBIZ_DESKTOP=1 and is excluded before this is even checked)."""
    if os.getenv("DURIELBIZ_DESKTOP") == "1":
        return False
    host = request.get_host().split(":")[0].lower()
    return host in {"127.0.0.1", "localhost"}


def is_cloud_request(request):
    if os.getenv("DURIELBIZ_DESKTOP") == "1":
        return False
    host = request.get_host().split(":")[0].lower()
    if host in {"127.0.0.1", "localhost"}:
        # Dev-only escape hatch so the cloud login variant can be previewed from
        # localhost without deploying. The real packaged desktop app can never reach
        # this branch — it always sets DURIELBIZ_DESKTOP=1 and returns above — so this
        # is safe to leave available regardless of DEBUG (which can vary per .env).
        mode = request.GET.get("mode")
        if mode in {"cloud", "local"}:
            request.session["dev_login_mode"] = mode
        if request.session.get("dev_login_mode") == "cloud":
            return True
        next_path = urlparse(request.GET.get("next", "")).path
        if next_path.startswith("/cloud/") or next_path == "/cloud":
            return True
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
        context["dev_login_preview"] = is_local_preview_eligible(self.request)
        return context

    def post(self, request, *args, **kwargs):
        throttle_key = f"login:{get_client_ip(request)}"
        if too_many_attempts(throttle_key, limit=8, window_seconds=900):
            form = self.get_form_class()(request, data=request.POST)
            form.add_error(None, "Too many failed login attempts. Please try again in a few minutes.")
            return self.render_to_response(self.get_context_data(form=form))
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        register_attempt(f"login:{get_client_ip(self.request)}", window_seconds=900)
        return super().form_invalid(form)


class CloudPasswordResetView(CloudModeRequiredMixin, View):
    """Step 1: collect the account email and, if it exists, email a one-time code."""

    template_name = "registration/password_reset_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": OTPRequestForm()})

    def post(self, request):
        form = OTPRequestForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        email = form.cleaned_data["email"]
        request.session["password_reset_email"] = email

        throttle_key = f"password-reset:{get_client_ip(request)}"
        if not throttle(throttle_key, limit=3, window_seconds=3600):
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                otp = create_otp(email, EmailOTP.Purpose.PASSWORD_RESET)
                try:
                    send_otp_email(
                        otp,
                        subject="Your DurielBiz password reset code",
                        template_name="registration/password_reset_otp_email.txt",
                    )
                except Exception:
                    otp.is_used = True
                    otp.save(update_fields=["is_used"])
                    logger.exception("Failed to send password reset OTP email to %s", email)
        return redirect("accounts:password-reset-done")


class CloudPasswordResetDoneView(CloudModeRequiredMixin, View):
    template_name = "registration/password_reset_done.html"

    def get(self, request):
        return render(request, self.template_name)


class CloudPasswordResetConfirmView(CloudModeRequiredMixin, View):
    """Step 2: verify the emailed code and set a new password."""

    template_name = "registration/password_reset_confirm.html"

    def get(self, request):
        email = request.session.get("password_reset_email")
        if not email:
            messages.error(request, "Start the password reset process again.")
            return redirect("accounts:password-reset")
        return render(request, self.template_name, {"form": OTPPasswordResetForm(), "email": email})

    def post(self, request):
        email = request.session.get("password_reset_email")
        if not email:
            messages.error(request, "Start the password reset process again.")
            return redirect("accounts:password-reset")

        throttle_key = f"password-reset-verify:{get_client_ip(request)}"
        if throttle(throttle_key, limit=8, window_seconds=900):
            messages.error(request, "Too many attempts. Request a new code and try again later.")
            return redirect("accounts:password-reset")

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        form = OTPPasswordResetForm(request.POST, user=user)
        form_valid = form.is_valid()

        otp = find_valid_otp(email, form.data.get("code", ""), EmailOTP.Purpose.PASSWORD_RESET) if user else None
        if not otp:
            form.add_error("code", "That code is invalid or has expired.")
            form_valid = False

        if form_valid:
            consume_otp(otp)
            user.set_password(form.cleaned_data["new_password1"])
            user.save(update_fields=["password"])
            request.session.pop("password_reset_email", None)
            log_activity(
                user=user,
                module=ActivityLog.Module.AUTH,
                action="password_reset_via_otp",
                description=f"{user.username} reset their password via an emailed verification code",
                entity_type="user",
                entity_id=user.pk,
                ip_address=get_client_ip(request),
            )
            return redirect("accounts:password-reset-complete")

        return render(request, self.template_name, {"form": form, "email": email})


class CloudPasswordResetCompleteView(CloudModeRequiredMixin, View):
    template_name = "registration/password_reset_complete.html"

    def get(self, request):
        return render(request, self.template_name)


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
    if request.user.must_change_password:
        return redirect("accounts:password-change-required")
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


@superadmin_required
def create_cloud_business(request):
    """DurielTech-only: create a cloud business account for a client and generate
    their initial password. The client is forced to change it on first login."""
    form = CreateCloudBusinessForm(request.POST or None)
    generated_password = None
    created_user = None

    if request.method == "POST" and form.is_valid():
        generated_password = secrets.token_urlsafe(9)
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            password=generated_password,
            role=User.Role.ADMIN,
        )
        user.must_change_password = True
        user.save(update_fields=["must_change_password"])

        business = CloudBusiness.objects.create(
            name=form.cleaned_data["business_name"],
            slug=form.cleaned_data["business_slug"],
            owner=user,
        )
        BusinessMembership.objects.create(user=user, business=business, role=BusinessMembership.Role.OWNER)
        SyncCredential.objects.create(business=business)

        log_activity(
            user=request.user,
            module=ActivityLog.Module.USERS,
            action="cloud_business_created",
            description=f"{request.user.username} created cloud business '{business.name}' for {user.username}",
            entity_type="business",
            entity_id=business.pk,
            metadata={"client_username": user.username, "client_email": user.email},
        )
        created_user = user
        messages.success(request, f"Cloud business '{business.name}' created. Copy the password below before leaving this page — it will not be shown again.")
        form = CreateCloudBusinessForm()

    return render(
        request,
        "accounts/create_cloud_business.html",
        {"form": form, "generated_password": generated_password, "created_user": created_user},
    )


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
def admin_reset_password(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        messages.info(request, "Use \"Change Password\" from the sidebar to update your own password.")
        return redirect("accounts:user-detail", pk=pk)

    if throttle(f"admin-reset:{request.user.pk}", limit=10, window_seconds=3600):
        messages.error(request, "Too many password resets attempted. Please try again in an hour.")
        return redirect("accounts:user-detail", pk=pk)

    form = StyledSetPasswordForm(target_user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        force_change = bool(request.POST.get("force_change_at_next_login"))
        form.save()
        target_user.must_change_password = force_change
        target_user.save(update_fields=["must_change_password"])
        log_activity(
            user=request.user,
            module=ActivityLog.Module.USERS,
            action="password_reset_by_admin",
            description=f"{request.user.username} reset the password for {target_user.username}",
            entity_type="user",
            entity_id=target_user.pk,
            metadata={"forced_change": force_change},
            ip_address=get_client_ip(request),
        )
        messages.success(request, f"Password for {target_user.username} has been reset.")
        return redirect("accounts:user-detail", pk=target_user.pk)

    return render(request, "accounts/admin_reset_password.html", {"form": form, "user_obj": target_user})


@login_required
def password_change_local(request):
    form = StyledSetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.user.must_change_password = False
        request.user.save(update_fields=["must_change_password"])
        log_activity(
            user=request.user,
            module=ActivityLog.Module.AUTH,
            action="password_changed",
            description=f"{request.user.username} changed their own password",
            entity_type="user",
            entity_id=request.user.pk,
        )
        messages.success(request, "Your password has been updated.")
        return redirect(get_role_home_url(request.user))

    return render(
        request,
        "accounts/password_change_local.html",
        {"form": form, "forced": request.user.must_change_password},
    )


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

    license_status = None
    if os.getenv("DURIELBIZ_DESKTOP") == "1" and settings.LICENSE_MASTER_KEY_HASH:
        from licensing.services import get_license_status

        license_status = get_license_status()

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
            "license_status": license_status,
            "deployment_modes": [
                "Works fully offline on this computer — sales keep going even without internet",
                "Can be viewed from other devices on the same Wi-Fi/network",
                "Optional cloud dashboard for checking sales remotely, from anywhere",
            ],
            "product_highlights": [
                "Fast checkout with barcode/name search and dual checkout lanes",
                "Multi-branch inventory, purchases, and stock tracking",
                "Customer loyalty points, discounts, and VAT support",
                "Receipts formatted for 58mm and 80mm thermal printers",
                "Sales, category, and profit reports with CSV/PDF export",
            ],
        },
    )
