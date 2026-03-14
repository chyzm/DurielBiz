import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import active_branches_for_user, get_user_branch, is_admin_user, role_required, scope_queryset_to_user_branch
from notifications.services import low_stock_products_queryset
from pos_system.pagination import paginate_queryset
from reports.models import Branch
from products.stock import product_queryset_for_branch

from .forms import InventoryAdjustmentForm
from .models import InventoryLog
from .services import apply_inventory_adjustment, delete_manual_adjustment, update_manual_adjustment


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def inventory_overview(request):
    branches = active_branches_for_user(request.user)
    if is_admin_user(request.user):
        branch_code = request.GET.get("branch", "").strip()
    else:
        branch_code = get_user_branch(request.user).code
    selected_branch = branches.filter(code=branch_code).first() if branch_code else None
    logs_queryset = scope_queryset_to_user_branch(
        InventoryLog.objects.select_related("product", "created_by", "branch"),
        request.user,
    ).order_by("-created_at")
    if branch_code:
        logs_queryset = logs_queryset.filter(branch__code=branch_code)

    recent_logs = paginate_queryset(
        request,
        logs_queryset,
        per_page=15,
        page_param="logs_page",
    )
    low_stock = paginate_queryset(request, low_stock_products_queryset(branch=selected_branch), per_page=8, page_param="stock_page")

    context = {
        "recent_logs": recent_logs,
        "low_stock_products": low_stock,
        "stock_additions": logs_queryset.filter(action=InventoryLog.Action.ADD).count(),
        "stock_removals": logs_queryset.filter(action=InventoryLog.Action.REMOVE).count(),
        "stock_adjustments": logs_queryset.filter(action=InventoryLog.Action.ADJUST).count(),
        "branches": branches,
        "selected_branch": branch_code,
        "selected_branch_name": selected_branch.name if selected_branch else "All Branches",
    }
    return render(request, "inventory/overview.html", context)


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def inventory_export_csv(request):
    if is_admin_user(request.user):
        branch_code = request.GET.get("branch", "").strip()
        selected_branch = Branch.objects.filter(code=branch_code, is_active=True).first() if branch_code else None
    else:
        selected_branch = get_user_branch(request.user)
    products = (
        product_queryset_for_branch(selected_branch)
        .select_related("category", "supplier")
        .order_by("name")
    )
    if selected_branch is not None and not is_admin_user(request.user):
        products = products.filter(branch_stocks__branch=selected_branch).distinct()

    response = HttpResponse(content_type="text/csv")
    branch_label = selected_branch.code if selected_branch else "all-branches"
    response["Content-Disposition"] = f'attachment; filename="inventory-{branch_label}.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Product",
            "Barcode",
            "Category",
            "Supplier",
            "Branch",
            "Current Stock",
            "Cost Price",
            "Selling Price",
            "Cost Worth",
            "Selling Worth",
            "Reorder Level",
            "Expiry Date",
        ]
    )

    for product in products:
        current_stock = int(product.branch_quantity if selected_branch else product.quantity)
        cost_worth = Decimal(current_stock) * product.cost_price
        selling_worth = Decimal(current_stock) * product.selling_price
        writer.writerow(
            [
                product.name,
                product.barcode or "",
                product.category.name,
                product.supplier.name if product.supplier else "",
                selected_branch.name if selected_branch else "All Branches",
                current_stock,
                product.cost_price,
                product.selling_price,
                cost_worth,
                selling_worth,
                product.reorder_level,
                product.expiry_date.isoformat() if product.expiry_date else "",
            ]
        )

    return response


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def inventory_adjustment(request):
    form = InventoryAdjustmentForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            apply_inventory_adjustment(
                branch=get_user_branch(request.user) or form.cleaned_data["branch"],
                product=form.cleaned_data["product"],
                action=form.cleaned_data["action"],
                quantity=form.cleaned_data["quantity"],
                reason=form.cleaned_data["reason"],
                reference=form.cleaned_data["reference"],
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            log_activity(
                user=request.user,
                module=ActivityLog.Module.INVENTORY,
                action="inventory_adjusted",
                description=f"{request.user.username} recorded a stock adjustment",
                entity_type="inventory_log",
            )
            messages.success(request, "Inventory updated successfully.")
            return redirect("inventory:overview")
    return render(request, "inventory/adjustment_form.html", {"form": form})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def inventory_detail(request, pk):
    log = get_object_or_404(
        scope_queryset_to_user_branch(InventoryLog.objects.select_related("product", "created_by", "branch"), request.user),
        pk=pk,
    )
    return render(request, "inventory/detail.html", {"log": log})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def inventory_update(request, pk):
    log = get_object_or_404(
        scope_queryset_to_user_branch(InventoryLog.objects.select_related("product"), request.user),
        pk=pk,
    )
    form = InventoryAdjustmentForm(
        request.POST or None,
        user=request.user,
        initial={
            "branch": log.branch,
            "product": log.product,
            "action": log.action,
            "quantity": log.after_quantity if log.action == InventoryLog.Action.ADJUST else abs(log.quantity),
            "reason": log.reason,
            "reference": log.reference,
        },
    )
    form.fields["branch"].disabled = True
    form.fields["product"].disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            updated_log = update_manual_adjustment(
                log=log,
                action=form.cleaned_data["action"],
                quantity=form.cleaned_data["quantity"],
                reason=form.cleaned_data["reason"],
                reference=form.cleaned_data["reference"],
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            log_activity(
                user=request.user,
                module=ActivityLog.Module.INVENTORY,
                action="inventory_adjustment_updated",
                description=f"{request.user.username} updated an inventory adjustment",
                entity_type="inventory_log",
                entity_id=updated_log.pk,
            )
            messages.success(request, "Adjustment updated successfully.")
            return redirect("inventory:detail", pk=updated_log.pk)
    return render(request, "inventory/adjustment_form.html", {"form": form, "log": log})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def inventory_delete(request, pk):
    log = get_object_or_404(
        scope_queryset_to_user_branch(InventoryLog.objects.select_related("product"), request.user),
        pk=pk,
    )
    if request.method == "POST":
        try:
            delete_manual_adjustment(log=log)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("inventory:detail", pk=pk)
        log_activity(
            user=request.user,
            module=ActivityLog.Module.INVENTORY,
            action="inventory_adjustment_deleted",
            description=f"{request.user.username} deleted an inventory adjustment",
            entity_type="inventory_log",
            entity_id=pk,
        )
        messages.success(request, "Adjustment deleted successfully.")
        return redirect("inventory:overview")
    return render(request, "inventory/confirm_delete.html", {"log": log})
