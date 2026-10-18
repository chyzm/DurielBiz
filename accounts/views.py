import logging
import os
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django import forms
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views import View

from pos_system.pagination import paginate_queryset
from pos_system.throttle import register_attempt, throttle, too_many_attempts

from .activity import get_client_ip, log_activity
from .forms import (
    EmailOrUsernameAuthenticationForm,
    OTPPasswordResetForm,
    OTPRequestForm,
    StaffUserCreationForm,
    StaffUserUpdateForm,
    StyledPasswordChangeForm,
    StyledSetPasswordForm,
)
from .otp import consume_otp, create_otp, find_valid_otp, send_otp_email
from .permissions import get_role_home_url, get_user_branch, role_required
from .subscriptions import add_subscription_term
from accounts.models import ActivityLog, Business, EmailOTP, SuperadminActivityLog, User
from accounts.tenancy import reset_current_business_id, set_current_business_id
from inventory.models import InventoryLog
from purchases.models import Purchase
from sales.models import Sale

logger = logging.getLogger(__name__)


class BusinessSetupForm(forms.Form):
    business_name = forms.CharField(max_length=255)
    admin_username = forms.CharField(max_length=150)
    admin_email = forms.EmailField()
    admin_password = forms.CharField(widget=forms.PasswordInput)
    subscription_plan = forms.ChoiceField(
        choices=Business.SubscriptionPlan.choices,
        initial=Business.SubscriptionPlan.YEARLY,
        label="Subscription",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "mt-2 block w-full rounded-xl border border-slate-300 bg-white px-4 py-3 "
            "text-sm text-slate-900 shadow-sm outline-none transition "
            "placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100"
        )
        placeholders = {
            "business_name": "e.g. Acme Stores",
            "admin_username": "Choose a username",
            "admin_email": "admin@example.com",
            "admin_password": "Create a strong password",
            "subscription_plan": "Choose a subscription term",
        }
        for name, field in self.fields.items():
            field.widget.attrs.update({"class": input_class, "placeholder": placeholders[name]})
        self.fields["admin_password"].widget.attrs["autocomplete"] = "new-password"

    def clean_admin_username(self):
        username = self.cleaned_data["admin_username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already in use.")
        return username

    def clean_admin_email(self):
        email = self.cleaned_data["admin_email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email address is already used by another user.")
        return email

    def clean_admin_password(self):
        from django.contrib.auth.password_validation import validate_password

        password = self.cleaned_data["admin_password"]
        validate_password(password)
        return password

    def save(self):
        name = self.cleaned_data["business_name"].strip()
        base_slug = slugify(name)[:110] or "business"
        slug, suffix = base_slug, 2
        while Business.objects.filter(slug=slug).exists():
            slug = f"{base_slug[:105]}-{suffix}"
            suffix += 1
        plan = self.cleaned_data["subscription_plan"]
        with transaction.atomic():
            business = Business.objects.create(
                name=name,
                slug=slug,
                subscription_plan=plan,
                subscription_expires_at=add_subscription_term(timezone.now(), plan),
            )
            admin = User.objects.create_user(
                username=self.cleaned_data["admin_username"],
                email=self.cleaned_data["admin_email"],
                password=self.cleaned_data["admin_password"],
                role=User.Role.ADMIN,
                business=business,
            )
            from reports.models import BusinessSettings

            token = set_current_business_id(business.pk)
            try:
                BusinessSettings.objects.create(business=business, business_name=name)
            finally:
                reset_current_business_id(token)
        return business, admin


def is_cloud_request(request):
    """True when this deployment is the centrally-hosted one rather than the packaged
    offline desktop app.

    Account self-service — the emailed OTP password reset and the password-change flow —
    needs a mail path, which the fully-offline desktop build does not have. This used to
    also distinguish the read-only cloud dashboard; that has been removed, so the check
    is now purely about deployment mode.

    Takes `request` for call-site compatibility; the answer no longer depends on it.
    """
    return os.getenv("DURIELBIZ_DESKTOP") != "1"


class CloudModeRequiredMixin:
    fallback_url = reverse_lazy("accounts:login")
    fallback_message = "This account action is available only on the hosted deployment."

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

    def form_valid(self, form):
        user = form.get_user()
        business = getattr(user, "business", None)
        if not user.is_superuser and business is not None:
            if not business.is_active:
                form.add_error(None, "This business account is inactive. Contact DurielTech to restore access.")
                return self.render_to_response(self.get_context_data(form=form))
            if business.subscription_expired:
                form.add_error(None, "This business subscription has expired. Contact the administrator to renew it.")
                return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


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
            matches = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
            # Do not send a reset code that could authenticate against the wrong tenant.
            user = matches[0] if len(matches) == 1 else None
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

        matches = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
        user = matches[0] if len(matches) == 1 else None
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
    if not request.user.business_id:
        if request.user.is_superuser:
            return redirect("accounts:business-setup")
        messages.error(request, "Your account is not assigned to a business.")
        return redirect("accounts:logout")
    if request.user.must_change_password:
        return redirect("accounts:password-change-required")
    return redirect(get_role_home_url(request.user))


@superadmin_required
def business_setup(request):
    form = BusinessSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        business, admin_user = form.save()
        SuperadminActivityLog.objects.create(
            user=request.user,
            business=business,
            action="business_created",
            description=f"Created business {business.name} and its first administrator",
            ip_address=get_client_ip(request),
        )
        messages.success(request, f"Business {business.name} and its administrator were created.")
        return redirect("accounts:superadmin-dashboard")
    return render(request, "accounts/business_setup.html", {"form": form})


@superadmin_required
def superadmin_dashboard(request):
    businesses = Business.objects.annotate(user_count=Count("users")).order_by("name")
    selected_business_id = request.GET.get("business", "").strip()
    activity_businesses = Business.objects.order_by("name")
    activities = SuperadminActivityLog.objects.select_related("user", "business").order_by("-created_at")
    if selected_business_id.isdigit():
        activities = activities.filter(business_id=int(selected_business_id))
    activity_page = paginate_queryset(request, activities, per_page=20, page_param="activity_page")
    context = {
        "businesses": businesses,
        "business_count": businesses.count(),
        "active_business_count": businesses.filter(is_active=True).count(),
        "expired_business_count": sum(1 for business in businesses if business.subscription_expired),
        "activity_businesses": activity_businesses,
        "activity_page": activity_page,
        "selected_business_id": selected_business_id,
    }
    return render(request, "accounts/superadmin_dashboard.html", context)


@superadmin_required
def superadmin_business_action(request, pk):
    if request.method != "POST":
        return redirect("accounts:superadmin-dashboard")
    action = request.POST.get("action", "")
    with transaction.atomic():
        business = get_object_or_404(Business.objects.select_for_update(), pk=pk)
        now = timezone.now()
        if action == "deactivate":
            business.is_active = False
            description = f"Superadmin deactivated business {business.name}"
        elif action == "activate":
            business.is_active = True
            description = f"Superadmin activated business {business.name}"
        elif action in {"renew_month", "renew_year"}:
            plan = Business.SubscriptionPlan.MONTHLY if action == "renew_month" else Business.SubscriptionPlan.YEARLY
            start_at = max(now, business.subscription_expires_at or now)
            business.subscription_plan = plan
            business.subscription_expires_at = add_subscription_term(start_at, plan)
            business.reminder_7_days_sent_at = None
            business.reminder_1_day_sent_at = None
            business.is_active = True
            description = f"Superadmin renewed business {business.name} for {business.get_subscription_plan_display()}"
        else:
            messages.error(request, "Choose a valid business action.")
            return redirect("accounts:superadmin-dashboard")
        business.save(update_fields=[
            "is_active", "subscription_plan", "subscription_expires_at",
            "reminder_7_days_sent_at", "reminder_1_day_sent_at",
        ])
        SuperadminActivityLog.objects.create(
            user=request.user,
            business=business,
            action=f"business_{action}",
            description=description,
            ip_address=get_client_ip(request),
        )
    messages.success(request, f"Updated {business.name}.")
    return redirect("accounts:superadmin-dashboard")


@superadmin_required
def superadmin_business_activity(request, pk):
    business = get_object_or_404(Business, pk=pk)
    tenant_token = set_current_business_id(business.pk)
    try:
        logs = ActivityLog.objects.select_related("user").filter(business=business).order_by("-created_at")
        logs_page = paginate_queryset(request, logs, per_page=20)
    finally:
        reset_current_business_id(tenant_token)
    return render(
        request,
        "accounts/superadmin_business_activity.html",
        {"business": business, "logs": logs_page},
    )


@login_required
@role_required(User.Role.ADMIN)
def admin_center(request):
    tenant_users = User.objects.filter(business=request.user.business)
    users_page = paginate_queryset(request, tenant_users.order_by("username"), per_page=10, page_param="users_page")
    context = {
        "staff_count": tenant_users.filter(is_staff=True).count(),
        "cashier_count": tenant_users.filter(role=User.Role.CASHIER).count(),
        "recent_sales_count": Sale.objects.filter(status=Sale.Status.COMPLETED).count(),
        "recent_purchase_count": Purchase.objects.count(),
        "inventory_event_count": InventoryLog.objects.count(),
        "users": users_page,
        "activity_count": ActivityLog.objects.count(),
        "users_page_obj": users_page,
    }
    return render(request, "accounts/admin_center.html", context)


@login_required
@role_required(User.Role.ADMIN)
def user_management(request):
    form = StaffUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.business = request.user.business
        user.save()
        form.save_m2m()
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
        "users": paginate_queryset(request, User.objects.filter(business=request.user.business).order_by("username"), per_page=10),
    }
    return render(request, "accounts/user_management.html", context)


@login_required
@role_required(User.Role.ADMIN)
def user_detail(request, pk):
    user_obj = get_object_or_404(User, pk=pk, business=request.user.business)
    return render(request, "accounts/user_detail.html", {"user_obj": user_obj})


@login_required
@role_required(User.Role.ADMIN)
def user_update(request, pk):
    user_obj = get_object_or_404(User, pk=pk, business=request.user.business)
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
    target_user = get_object_or_404(User, pk=pk, business=request.user.business)
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
    user_obj = get_object_or_404(User, pk=pk, business=request.user.business)
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
@role_required(User.Role.ADMIN, User.Role.MANAGER)
def activity_log_list(request):
    module = request.GET.get("module", "").strip()
    logs = ActivityLog.objects.select_related("user").order_by("-created_at")
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        logs = logs.filter(user__branch=user_branch)
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
    license_status = None
    if os.getenv("DURIELBIZ_DESKTOP") == "1" and settings.LICENSE_MASTER_KEY_HASH:
        from licensing.services import get_license_status

        license_status = get_license_status()

    business = getattr(request.user, "business", None)

    return render(
        request,
        "accounts/about_support.html",
        {
            "support_phone": "07031016787",
            "support_email": "info@durieltech.com.ng",
            "company_name": "DurielTech",
            "product_name": "DurielBiz POS",
            "app_version": "1.0.0",
            "license_status": license_status,
            "business": business,
            "deployment_modes": [
                "Works fully offline on this computer — sales keep going even without internet",
                "Can be reached from other devices on the same Wi-Fi/network",
                "Can also run hosted, with data synced between the two",
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
