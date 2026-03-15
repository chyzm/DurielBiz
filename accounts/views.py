from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from pos_system.pagination import paginate_queryset

from cloudsync.services import user_business
from .activity import log_activity
from .forms import StaffUserCreationForm, StaffUserUpdateForm
from .permissions import get_role_home_url, role_required
from accounts.models import ActivityLog, User
from inventory.models import InventoryLog
from purchases.models import Purchase
from sales.models import Sale


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
