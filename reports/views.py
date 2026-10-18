import csv
import json
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
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
    profit_by_product_report,
    render_profit_report_pdf,
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
def branch_list(request):
    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save()
        if not BusinessSettings.get_solo().default_branch:
            settings_obj = BusinessSettings.get_solo()
            settings_obj.default_branch = branch
            settings_obj.save(update_fields=["default_branch", "updated_at"])
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
            settings_obj = BusinessSettings.get_solo()
            settings_obj.default_branch = None
            settings_obj.save(update_fields=["default_branch", "updated_at"])
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
    branches = active_branches_for_user(request.user)
    if request.user.role == User.Role.ADMIN:
        branch_code = request.GET.get("branch", "").strip()
        branch_obj = branches.filter(code=branch_code).first() if branch_code else None
    else:
        branch_obj = get_user_branch(request.user)
        branch_code = branch_obj.code if branch_obj else ""

    today = timezone.localdate()
    default_start = (today - timedelta(days=29)).isoformat()
    default_end = today.isoformat()
    start_date = request.GET.get("start_date", "").strip() or default_start
    end_date = request.GET.get("end_date", "").strip() or default_end
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start > end:
            raise ValueError("start date is after end date")
    except ValueError:
        messages.warning(request, "The date range was invalid; showing the default 30-day period.")
        start_date, end_date = default_start, default_end
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)

    return {
        "branches": branches,
        "selected_branch": branch_code,
        "branch_obj": branch_obj,
        "branch_label": branch_obj.name if branch_obj else "All Branches",
        "start_date": start_date,
        "end_date": end_date,
        "start": start,
        "end": end,
    }


@login_required
@role_required(User.Role.ADMIN, User.Role.MANAGER)
def reports_category(request):
    filters = _report_filters(request)
    rows = category_sales_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"])
    return render(
        request,
        "reports/category_report.html",
        {**filters, "rows": paginate_queryset(request, rows, per_page=20)},
    )


@login_required
@role_required(User.Role.ADMIN, User.Role.MANAGER)
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
@role_required(User.Role.ADMIN, User.Role.MANAGER)
def reports_profit_by_product(request):
    filters = _report_filters(request)
    rows = profit_by_product_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"])
    return render(
        request,
        "reports/profit_by_product.html",
        {**filters, "rows": paginate_queryset(request, rows, per_page=20)},
    )


@login_required
@role_required(User.Role.ADMIN, User.Role.MANAGER)
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
@role_required(User.Role.ADMIN, User.Role.MANAGER)
def reports_profit_export_pdf(request):
    filters = _report_filters(request)
    rows = list(profit_by_product_report(branch=filters["branch_obj"], start_date=filters["start"], end_date=filters["end"]))
    return render_profit_report_pdf(
        rows, branch_name=filters["branch_label"], start_date=filters["start_date"], end_date=filters["end_date"]
    )
