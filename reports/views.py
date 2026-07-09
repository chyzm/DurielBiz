import csv
import json
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import active_branches_for_user, get_user_branch, role_required
from pos_system.pagination import paginate_queryset

from .forms import BranchForm, BusinessSettingsForm
from .models import Branch, BusinessSettings
from .services import (
    category_sales_report,
    dashboard_metrics,
    perform_cloud_sync,
    profit_by_product_report,
    render_profit_report_pdf,
    sync_export_payload,
)


def home(request):
    host = request.get_host().split(":", 1)[0].lower()
    is_local_dev = host in {"127.0.0.1", "localhost"} and os.getenv("DURIELBIZ_DESKTOP") != "1"
    tools_url = reverse("invoicing:home") if settings.INVOICING_ALLOW_LOCAL or is_local_dev else f"{settings.DURIELBIZ_SITE_URL.rstrip('/')}/tools/"
    return render(
        request,
        "home.html",
        {
            "tools_url": tools_url,
        },
    )


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
def sync_now(request):
    settings_obj = BusinessSettings.get_solo()
    if request.method != "POST":
        return redirect("reports:business-settings")
    if not settings_obj.cloud_sync_enabled:
        messages.error(request, "Enable cloud sync first.")
        return redirect("reports:business-settings")
    if not settings_obj.cloud_sync_token or not settings_obj.sync_dashboard_url:
        messages.error(request, "Set both cloud sync token and sync dashboard URL first.")
        return redirect("reports:business-settings")
    try:
        response = perform_cloud_sync(settings_obj=settings_obj)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        log_activity(
            user=request.user,
            module=ActivityLog.Module.SETTINGS,
            action="cloud_sync_triggered",
            description=f"{request.user.username} triggered a cloud sync",
            entity_type="business_settings",
            entity_id=settings_obj.pk,
            metadata=response if isinstance(response, dict) else {},
        )
        messages.success(request, "Cloud sync completed successfully.")
    return redirect("reports:business-settings")


@login_required
def sync_auto(request):
    settings_obj = BusinessSettings.get_solo()
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed."}, status=405)
    if not settings_obj.cloud_sync_enabled or not settings_obj.auto_sync_enabled:
        return JsonResponse({"ok": False, "message": "Automatic cloud sync is disabled."}, status=400)
    if not settings_obj.cloud_sync_token or not settings_obj.sync_dashboard_url:
        return JsonResponse({"ok": False, "message": "Cloud sync token or URL is missing."}, status=400)
    try:
        response = perform_cloud_sync(settings_obj=settings_obj)
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "message": "Automatic cloud sync completed.",
            "last_cloud_sync_at": settings_obj.last_cloud_sync_at.isoformat() if settings_obj.last_cloud_sync_at else "",
            "response": response if isinstance(response, dict) else {},
        }
    )


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


def _report_filters(request):
    branches = Branch.objects.filter(is_active=True).order_by("name")
    branch_code = request.GET.get("branch", "").strip()
    branch_obj = branches.filter(code=branch_code).first() if branch_code else None

    today = timezone.localdate()
    default_start = (today - timedelta(days=29)).isoformat()
    default_end = today.isoformat()
    start_date = request.GET.get("start_date", "").strip() or default_start
    end_date = request.GET.get("end_date", "").strip() or default_end

    return {
        "branches": branches,
        "selected_branch": branch_code,
        "branch_obj": branch_obj,
        "branch_label": branch_obj.name if branch_obj else "All Branches",
        "start_date": start_date,
        "end_date": end_date,
        "start": datetime.strptime(start_date, "%Y-%m-%d").date(),
        "end": datetime.strptime(end_date, "%Y-%m-%d").date(),
    }


@login_required
@role_required(User.Role.ADMIN)
def reports_category(request):
    filters = _report_filters(request)
    rows = category_sales_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"])
    return render(
        request,
        "reports/category_report.html",
        {**filters, "rows": paginate_queryset(request, rows, per_page=20)},
    )


@login_required
@role_required(User.Role.ADMIN)
def reports_category_export_csv(request):
    filters = _report_filters(request)
    rows = category_sales_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"])
    filename = f"category-report-{filters['start_date']}-to-{filters['end_date']}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(["Category", "Quantity Sold", "Revenue", "Profit"])
    for row in rows:
        writer.writerow(
            [row["product__category__name"] or "Uncategorized", row["quantity_sold"] or 0, row["revenue"] or 0, row["profit"] or 0]
        )
    return response


@login_required
@role_required(User.Role.ADMIN)
def reports_profit_by_product(request):
    filters = _report_filters(request)
    rows = profit_by_product_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"])
    return render(
        request,
        "reports/profit_by_product.html",
        {**filters, "rows": paginate_queryset(request, rows, per_page=20)},
    )


@login_required
@role_required(User.Role.ADMIN)
def reports_profit_export_csv(request):
    filters = _report_filters(request)
    rows = profit_by_product_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"])
    filename = f"profit-by-product-{filters['start_date']}-to-{filters['end_date']}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(["Product", "Category", "Quantity Sold", "Revenue", "Profit"])
    for row in rows:
        writer.writerow(
            [
                row["product__name"],
                row["product__category__name"] or "Uncategorized",
                row["quantity_sold"] or 0,
                row["revenue"] or 0,
                row["profit"] or 0,
            ]
        )
    return response


@login_required
@role_required(User.Role.ADMIN)
def reports_profit_export_pdf(request):
    filters = _report_filters(request)
    rows = list(profit_by_product_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"]))
    return render_profit_report_pdf(
        rows, branch_name=filters["branch_label"], start_date=filters["start_date"], end_date=filters["end_date"]
    )


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
