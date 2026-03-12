from django.db import transaction

from django.core.exceptions import ValidationError

from inventory.models import InventoryLog
from products.models import Product
from products.stock import apply_global_delta, get_branch_stock

from .models import PurchaseItem


@transaction.atomic
def receive_purchase(*, purchase, items, actor=None):
    created_items = []

    for raw_item in items:
        product = Product.objects.select_for_update().get(pk=raw_item["product_id"])
        quantity = int(raw_item["quantity"])
        cost_price = raw_item["cost_price"]
        expiry_date = raw_item.get("expiry_date")

        purchase_item = PurchaseItem.objects.create(
            purchase=purchase,
            product=product,
            quantity=quantity,
            cost_price=cost_price,
            expiry_date=expiry_date,
        )
        created_items.append(purchase_item)

        branch_stock = get_branch_stock(product, purchase.branch) if purchase.branch else None
        before_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
        after_quantity = before_quantity + quantity
        if branch_stock is not None:
            branch_stock.quantity = after_quantity
            branch_stock.save(update_fields=["quantity", "updated_at"])
            apply_global_delta(product, quantity)
        else:
            product.quantity = after_quantity
        product.cost_price = cost_price
        if expiry_date:
            product.expiry_date = expiry_date
        product.save(update_fields=["quantity", "cost_price", "expiry_date", "updated_at"])

        InventoryLog.objects.create(
            product=product,
            branch=purchase.branch,
            quantity=quantity,
            action=InventoryLog.Action.ADD,
            source=InventoryLog.Source.PURCHASE,
            reason="Purchase received",
            reference=purchase.inventory_reference,
            before_quantity=before_quantity,
            after_quantity=after_quantity,
            created_by=actor,
        )

    return created_items


@transaction.atomic
def reverse_purchase(*, purchase, delete_logs=False):
    for item in purchase.items.select_related("product").all():
        product = Product.objects.select_for_update().get(pk=item.product_id)
        branch_stock = get_branch_stock(product, purchase.branch) if purchase.branch else None
        available_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
        if available_quantity < item.quantity:
            raise ValidationError(
                f"Cannot reverse purchase {purchase.invoice_no}; {product.name} stock has fallen below received quantity."
            )
        if branch_stock is not None:
            branch_stock.quantity -= item.quantity
            branch_stock.save(update_fields=["quantity", "updated_at"])
            apply_global_delta(product, -item.quantity)
        else:
            product.quantity -= item.quantity
            product.save(update_fields=["quantity", "updated_at"])

    if delete_logs:
        InventoryLog.objects.filter(
            source=InventoryLog.Source.PURCHASE,
            reference=purchase.inventory_reference,
        ).delete()


@transaction.atomic
def update_purchase(*, purchase, branch, supplier, invoice_no, received_at, notes, items, actor=None):
    reverse_purchase(purchase=purchase, delete_logs=True)
    purchase.items.all().delete()

    purchase.branch = branch
    purchase.supplier = supplier
    purchase.invoice_no = invoice_no
    purchase.received_at = received_at
    purchase.notes = notes
    purchase.created_by = actor or purchase.created_by
    purchase.save()

    receive_purchase(purchase=purchase, items=items, actor=actor)

    return purchase


@transaction.atomic
def delete_purchase(*, purchase):
    reverse_purchase(purchase=purchase, delete_logs=True)
    purchase.items.all().delete()
    purchase.delete()
