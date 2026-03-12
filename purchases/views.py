from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import active_branches_for_user, get_user_branch, is_admin_user, role_required, scope_queryset_to_user_branch
from pos_system.pagination import paginate_queryset
from reports.models import Branch, BusinessSettings

from .forms import PurchaseReceiveForm
from .models import Purchase
from .services import delete_purchase, receive_purchase, update_purchase


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def purchase_list(request):
    branches = active_branches_for_user(request.user)
    purchases = Purchase.objects.select_related("supplier", "created_by", "branch").prefetch_related("items", "items__product")
    purchases = scope_queryset_to_user_branch(purchases, request.user)
    if is_admin_user(request.user):
        branch_code = request.GET.get("branch", "").strip()
    else:
        branch_code = get_user_branch(request.user).code
    if branch_code:
        purchases = purchases.filter(branch__code=branch_code)
    purchases = purchases.order_by("-received_at")
    purchases_page = paginate_queryset(request, purchases, per_page=10)
    selected_branch = branches.filter(code=branch_code).first() if branch_code else None

    context = {
        "purchases": purchases_page,
        "purchase_count": purchases.count(),
        "supplier_count": purchases.values("supplier").distinct().count(),
        "item_count": purchases.aggregate(total=Count("items"))["total"] or 0,
        "branches": branches,
        "selected_branch": branch_code,
        "selected_branch_name": selected_branch.name if selected_branch else "All Branches",
    }
    return render(request, "purchases/purchase_list.html", context)


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def purchase_create(request):
    form = PurchaseReceiveForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        purchase_branch = get_user_branch(request.user) or form.cleaned_data["branch"] or BusinessSettings.get_solo().default_branch
        purchase = Purchase.objects.create(
            branch=purchase_branch,
            supplier=form.cleaned_data["supplier"],
            invoice_no=form.cleaned_data["invoice_no"],
            received_at=form.cleaned_data["received_at"],
            created_by=request.user,
            notes=form.cleaned_data["notes"],
        )
        receive_purchase(
            purchase=purchase,
            items=[
                {
                    "product_id": form.cleaned_data["product"].pk,
                    "quantity": form.cleaned_data["quantity"],
                    "cost_price": form.cleaned_data["cost_price"],
                    "expiry_date": form.cleaned_data["expiry_date"],
                }
            ],
            actor=request.user,
        )
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PURCHASES,
            action="purchase_created",
            description=f"{request.user.username} received purchase {purchase.invoice_no}",
            entity_type="purchase",
            entity_id=purchase.pk,
        )
        messages.success(request, f"Purchase {purchase.invoice_no} received successfully.")
        return redirect("purchases:list")
    return render(request, "purchases/purchase_form.html", {"form": form})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def purchase_detail(request, pk):
    purchase = get_object_or_404(
        scope_queryset_to_user_branch(
            Purchase.objects.select_related("supplier", "created_by", "branch").prefetch_related("items", "items__product"),
            request.user,
        ),
        pk=pk,
    )
    items_page = paginate_queryset(request, purchase.items.select_related("product").all(), per_page=10, page_param="items_page")
    return render(request, "purchases/purchase_detail.html", {"purchase": purchase, "items": items_page})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def purchase_update(request, pk):
    purchase = get_object_or_404(scope_queryset_to_user_branch(Purchase.objects.prefetch_related("items"), request.user), pk=pk)
    first_item = purchase.items.select_related("product").first()
    initial = {
        "branch": purchase.branch,
        "supplier": purchase.supplier,
        "invoice_no": purchase.invoice_no,
        "received_at": purchase.received_at.strftime("%Y-%m-%dT%H:%M"),
        "notes": purchase.notes,
    }
    if first_item:
        initial.update(
            {
                "product": first_item.product,
                "quantity": first_item.quantity,
                "cost_price": first_item.cost_price,
                "expiry_date": first_item.expiry_date,
            }
        )
    form = PurchaseReceiveForm(request.POST or None, initial=initial, purchase=purchase, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            update_purchase(
                purchase=purchase,
                branch=get_user_branch(request.user) or form.cleaned_data["branch"] or BusinessSettings.get_solo().default_branch,
                supplier=form.cleaned_data["supplier"],
                invoice_no=form.cleaned_data["invoice_no"],
                received_at=form.cleaned_data["received_at"],
                notes=form.cleaned_data["notes"],
                items=[
                    {
                        "product_id": form.cleaned_data["product"].pk,
                        "quantity": form.cleaned_data["quantity"],
                        "cost_price": form.cleaned_data["cost_price"],
                        "expiry_date": form.cleaned_data["expiry_date"],
                    }
                ],
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            log_activity(
                user=request.user,
                module=ActivityLog.Module.PURCHASES,
                action="purchase_updated",
                description=f"{request.user.username} updated purchase {purchase.invoice_no}",
                entity_type="purchase",
                entity_id=purchase.pk,
            )
            messages.success(request, f"Purchase {purchase.invoice_no} updated successfully.")
            return redirect("purchases:detail", pk=purchase.pk)
    return render(request, "purchases/purchase_form.html", {"form": form, "purchase": purchase})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def purchase_delete(request, pk):
    purchase = get_object_or_404(
        scope_queryset_to_user_branch(Purchase.objects.prefetch_related("items", "items__product"), request.user),
        pk=pk,
    )
    if request.method == "POST":
        try:
            delete_purchase(purchase=purchase)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("purchases:detail", pk=pk)
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PURCHASES,
            action="purchase_deleted",
            description=f"{request.user.username} deleted purchase {purchase.invoice_no}",
            entity_type="purchase",
            entity_id=pk,
        )
        messages.success(request, f"Purchase {purchase.invoice_no} deleted successfully.")
        return redirect("purchases:list")
    return render(request, "purchases/purchase_confirm_delete.html", {"purchase": purchase})
