from django.db import transaction

from django.core.exceptions import ValidationError
from django.utils import timezone

from inventory.models import InventoryLog
from products.models import Product
from products.stock import apply_global_delta, get_branch_stock

from .models import PurchaseCorrectionEvent, PurchaseItem


def _lock_products(product_ids):
    ids = sorted(set(product_ids))
    return {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    }


@transaction.atomic
def receive_purchase(*, purchase, items, actor=None):
    items = list(items)
    created_items = []
    products = _lock_products(raw_item["product_id"] for raw_item in items)

    for raw_item in items:
        product = products.get(raw_item["product_id"])
        if product is None:
            raise ValidationError("A selected product no longer exists.")
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
def reverse_purchase(*, purchase, delete_logs=False, actor=None):
    """Reverse received stock with compensating ledger rows; keep original logs."""
    items = list(purchase.items.filter(is_current=True).select_related("product").order_by("product_id", "pk"))
    products = _lock_products(item.product_id for item in items)
    event_reference = f"{purchase.inventory_reference}:reversal:{timezone.now():%Y%m%d%H%M%S%f}"
    for item in items:
        product = products.get(item.product_id)
        if product is None:
            raise ValidationError("A product from this purchase no longer exists.")
        branch_stock = get_branch_stock(product, purchase.branch) if purchase.branch else None
        available_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
        if available_quantity < item.quantity:
            raise ValidationError(
                f"Cannot reverse purchase {purchase.invoice_no}; {product.name} stock has fallen below received quantity."
            )
        if branch_stock is not None:
            before_quantity = branch_stock.quantity
            branch_stock.quantity -= item.quantity
            branch_stock.save(update_fields=["quantity", "updated_at"])
            apply_global_delta(product, -item.quantity)
        else:
            before_quantity = product.quantity
            product.quantity -= item.quantity
            product.save(update_fields=["quantity", "updated_at"])
        InventoryLog.objects.create(
            product=product,
            branch=purchase.branch,
            quantity=-item.quantity,
            action=InventoryLog.Action.REMOVE,
            source=InventoryLog.Source.PURCHASE,
            reason="Purchase quantity reversed",
            reference=event_reference,
            before_quantity=before_quantity,
            after_quantity=before_quantity - item.quantity,
            created_by=actor,
        )


@transaction.atomic
def update_purchase(*, purchase, branch, supplier, invoice_no, received_at, notes, items, actor=None):
    prior_items = list(purchase.items.filter(is_current=True).select_related("product"))
    before = {
        "branch_id": purchase.branch_id,
        "supplier_id": purchase.supplier_id,
        "invoice_no": purchase.invoice_no,
        "received_at": purchase.received_at.isoformat(),
        "notes": purchase.notes,
        "items": [
            {"id": line.pk, "product_id": line.product_id, "product": line.product.name,
             "quantity": line.quantity, "cost_price": str(line.cost_price),
             "expiry_date": line.expiry_date.isoformat() if line.expiry_date else None}
            for line in prior_items
        ],
    }
    reverse_purchase(purchase=purchase, actor=actor)
    for line in prior_items:
        line.is_current = False
        line.save(update_fields=["is_current"])

    purchase.branch = branch
    purchase.supplier = supplier
    purchase.invoice_no = invoice_no
    purchase.received_at = received_at
    purchase.notes = notes
    purchase.created_by = actor or purchase.created_by
    purchase.save()

    created_items = receive_purchase(purchase=purchase, items=items, actor=actor)
    PurchaseCorrectionEvent.objects.create(
        business_id=purchase.business_id, purchase=purchase, action=PurchaseCorrectionEvent.Action.EDITED,
        before=before,
        after={"branch_id": branch.pk if branch else None, "supplier_id": supplier.pk,
               "invoice_no": invoice_no, "received_at": received_at.isoformat(), "notes": notes,
               "items": [{"id": line.pk, "product_id": line.product_id, "quantity": line.quantity,
                          "cost_price": str(line.cost_price),
                          "expiry_date": line.expiry_date.isoformat() if line.expiry_date else None}
                         for line in created_items]},
        actor=actor,
    )

    return purchase


@transaction.atomic
def delete_purchase(*, purchase, actor=None):
    lines = list(purchase.items.filter(is_current=True).select_related("product"))
    before = {
        "branch_id": purchase.branch_id, "supplier_id": purchase.supplier_id,
        "invoice_no": purchase.invoice_no, "received_at": purchase.received_at.isoformat(),
        "notes": purchase.notes,
        "items": [{"id": line.pk, "product_id": line.product_id, "product": line.product.name,
                   "quantity": line.quantity, "cost_price": str(line.cost_price),
                   "expiry_date": line.expiry_date.isoformat() if line.expiry_date else None}
                  for line in lines],
    }
    reverse_purchase(purchase=purchase, actor=actor)
    for line in lines:
        line.is_current = False
        line.save(update_fields=["is_current"])
    PurchaseCorrectionEvent.objects.create(
        business_id=purchase.business_id, purchase=purchase, action=PurchaseCorrectionEvent.Action.DELETED,
        before=before, actor=actor,
    )
    purchase.is_archived = True
    purchase.save(update_fields=["is_archived"])
