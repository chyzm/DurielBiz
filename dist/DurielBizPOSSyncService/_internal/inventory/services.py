from django.core.exceptions import ValidationError
from django.db import transaction

from products.stock import apply_global_delta, get_branch_stock
from reports.services import current_branch

from .models import InventoryLog


@transaction.atomic
def apply_inventory_adjustment(*, product, action, quantity, reason, reference="", actor=None, branch=None):
    branch = branch or current_branch()
    branch_stock = get_branch_stock(product, branch) if branch else None
    current_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
    quantity = int(quantity)

    if action == InventoryLog.Action.ADD:
        after_quantity = current_quantity + quantity
        logged_quantity = quantity
    elif action == InventoryLog.Action.REMOVE:
        if quantity > current_quantity:
            raise ValidationError(f"Cannot remove {quantity}; only {current_quantity} in stock.")
        after_quantity = current_quantity - quantity
        logged_quantity = quantity
    else:
        if quantity < 0:
            raise ValidationError("Adjusted quantity cannot be negative.")
        after_quantity = quantity
        logged_quantity = quantity - current_quantity

    if branch_stock is not None:
        branch_stock.quantity = after_quantity
        branch_stock.save(update_fields=["quantity", "updated_at"])
        apply_global_delta(product, after_quantity - current_quantity)
    else:
        product.quantity = after_quantity
        product.save(update_fields=["quantity", "updated_at"])

    return InventoryLog.objects.create(
        product=product,
        branch=branch,
        quantity=logged_quantity,
        action=action,
        source=InventoryLog.Source.MANUAL,
        reason=reason,
        reference=reference,
        before_quantity=current_quantity,
        after_quantity=after_quantity,
        created_by=actor,
    )


@transaction.atomic
def update_manual_adjustment(*, log, action, quantity, reason, reference="", actor=None):
    if log.source != InventoryLog.Source.MANUAL:
        raise ValidationError("Only manual adjustments can be edited here.")
    if InventoryLog.objects.filter(product=log.product, branch=log.branch, created_at__gt=log.created_at).exists():
        raise ValidationError("Only the latest stock event for this product can be edited.")

    product = log.product
    branch_stock = get_branch_stock(product, log.branch) if log.branch else None
    current_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
    if branch_stock is not None:
        branch_stock.quantity = log.before_quantity
        branch_stock.save(update_fields=["quantity", "updated_at"])
        apply_global_delta(product, log.before_quantity - current_quantity)
    else:
        product.quantity = log.before_quantity
        product.save(update_fields=["quantity", "updated_at"])

    updated_log = apply_inventory_adjustment(
        product=product,
        action=action,
        quantity=quantity,
        reason=reason,
        reference=reference,
        actor=actor,
        branch=log.branch,
    )
    log.delete()
    return updated_log


@transaction.atomic
def delete_manual_adjustment(*, log):
    if log.source != InventoryLog.Source.MANUAL:
        raise ValidationError("Only manual adjustments can be deleted here.")
    if InventoryLog.objects.filter(product=log.product, branch=log.branch, created_at__gt=log.created_at).exists():
        raise ValidationError("Only the latest stock event for this product can be deleted.")

    product = log.product
    branch_stock = get_branch_stock(product, log.branch) if log.branch else None
    current_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
    if branch_stock is not None:
        branch_stock.quantity = log.before_quantity
        branch_stock.save(update_fields=["quantity", "updated_at"])
        apply_global_delta(product, log.before_quantity - current_quantity)
    else:
        product.quantity = log.before_quantity
        product.save(update_fields=["quantity", "updated_at"])
    log.delete()
