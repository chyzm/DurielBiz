import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import active_branches_for_user, get_user_branch, role_required
from pos_system.pagination import paginate_queryset

from .forms import BranchForm, BusinessSettingsForm
from .models import Branch, BusinessSettings
from .services import dashboard_metrics, sync_export_payload


@login_required
@role_required(User.Role.ADMIN, User.Role.CASHIER, User.Role.MANAGER)
def dashboard(request):
    branches = active_branches_for_user(request.user)
    if request.user.role == User.Role.ADMIN:
        branch_code = request.GET.get("branch", "").strip()
        selected_branch = branches.filter(code=branch_code).first() if branch_code else None
    else:
        selected_branch = get_user_branch(request.user)
        branch_code = selected_branch.code if selected_branch else ""

    metrics = dashboard_metrics(branch=selected_branch)
    top_products = paginate_queryset(request, metrics["top_products"], per_page=5, page_param="top_page")
    low_stock = paginate_queryset(request, metrics["low_stock"], per_page=5, page_param="low_page")
    expiring_products = paginate_queryset(request, metrics["expiring_products"], per_page=5, page_param="exp_page")
    return render(
        request,
        "reports/dashboard.html",
        {
            **metrics,
            "top_products": top_products,
            "low_stock": low_stock,
            "expiring_products": expiring_products,
            "expiring_count": metrics["expiring_products"].count(),
            "sales_chart_json": json.dumps(metrics["sales_chart"]),
            "branches": branches,
            "selected_branch": branch_code,
        },
    )


@login_required
@role_required(User.Role.ADMIN)
def business_settings_view(request):
    settings_obj = BusinessSettings.get_solo()
    form = BusinessSettingsForm(request.POST or None, instance=settings_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.SETTINGS,
            action="business_settings_updated",
            description=f"{request.user.username} updated business settings",
            entity_type="business_settings",
            entity_id=settings_obj.pk,
        )
        messages.success(request, "Business settings updated successfully.")
        return redirect("reports:business-settings")
    return render(request, "reports/business_settings.html", {"form": form})


@login_required
@role_required(User.Role.ADMIN)
def branch_list(request):
    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save()
        if not BusinessSettings.get_solo().default_branch:
            BusinessSettings.objects.filter(pk=BusinessSettings.get_solo().pk).update(default_branch=branch)
        log_activity(
            user=request.user,
            module=ActivityLog.Module.SETTINGS,
            action="branch_created",
            description=f"{request.user.username} created branch {branch.name}",
            entity_type="branch",
            entity_id=branch.pk,
        )
        messages.success(request, f"Branch {branch.name} created successfully.")
        return redirect("reports:branch-list")

    branches = paginate_queryset(request, Branch.objects.order_by("name"), per_page=10)
    return render(request, "reports/branch_list.html", {"form": form, "branches": branches})


@login_required
@role_required(User.Role.ADMIN)
def branch_update(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.SETTINGS,
            action="branch_updated",
            description=f"{request.user.username} updated branch {branch.name}",
            entity_type="branch",
            entity_id=branch.pk,
        )
        messages.success(request, f"Branch {branch.name} updated successfully.")
        return redirect("reports:branch-list")
    return render(request, "reports/branch_form.html", {"form": form, "branch": branch})


@login_required
@role_required(User.Role.ADMIN)
def branch_delete(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == "POST":
        branch_name = branch.name
        if BusinessSettings.get_solo().default_branch_id == branch.pk:
            BusinessSettings.objects.filter(pk=BusinessSettings.get_solo().pk).update(default_branch=None)
        branch.delete()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.SETTINGS,
            action="branch_deleted",
            description=f"{request.user.username} deleted branch {branch_name}",
            entity_type="branch",
            entity_id=pk,
        )
        messages.success(request, f"Branch {branch_name} deleted successfully.")
        return redirect("reports:branch-list")
    return render(request, "reports/branch_confirm_delete.html", {"branch": branch})


def sync_export_view(request):
    settings_obj = BusinessSettings.get_solo()
    token = request.headers.get("X-Sync-Token") or request.GET.get("token", "").strip()
    user = getattr(request, "user", None)
    is_admin_user = bool(user and user.is_authenticated and getattr(user, "role", "") == User.Role.ADMIN)

    if not settings_obj.cloud_sync_enabled and not is_admin_user:
        return HttpResponseForbidden("Cloud sync is disabled.")
    if not is_admin_user and (not settings_obj.cloud_sync_token or token != settings_obj.cloud_sync_token):
        return HttpResponseForbidden("Invalid sync token.")

    scoped_branch = None
    if user and user.is_authenticated and getattr(user, "role", "") != User.Role.ADMIN:
        scoped_branch = get_user_branch(user)

    payload = sync_export_payload(since=request.GET.get("since"), branch=scoped_branch)
    return JsonResponse(payload)
