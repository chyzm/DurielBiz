from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.permissions import get_user_branch
from inventory.models import InventoryLog
from products.models import Product
from products.stock import apply_global_delta, get_branch_stock
from reports.models import BusinessSettings

from .models import Customer, Sale, SaleItem


@transaction.atomic
def create_sale(
    *,
    cashier,
    items,
    payment_method,
    paid_amount,
    customer_name="",
    customer_phone="",
    note="",
    lane_name="checkout_a",
    redeemed_points=0,
    discount=Decimal("0.00"),
    tax=Decimal("0.00"),
):
    customer = None
    business_settings = BusinessSettings.get_solo()
    sale_branch = get_user_branch(cashier) or business_settings.default_branch
    if customer_phone:
        customer, created = Customer.objects.get_or_create(
            phone=customer_phone,
            defaults={"name": customer_name or customer_phone},
        )
        if customer_name and customer.name != customer_name:
            customer.name = customer_name
            customer.save(update_fields=["name", "updated_at"])

    redeemed_points = int(redeemed_points or 0)
    if redeemed_points and not customer:
        raise ValidationError("Redeeming points requires a saved customer phone number.")
    if customer and redeemed_points > customer.loyalty_points:
        raise ValidationError("Customer does not have enough loyalty points.")
    redeemed_amount = Decimal(redeemed_points) * business_settings.loyalty_cash_value_per_point

    sale = Sale.objects.create(
        cashier=cashier,
        branch=sale_branch,
        customer=customer,
        customer_name=customer_name,
        customer_phone=customer_phone,
        redeemed_points=redeemed_points,
        redeemed_amount=redeemed_amount,
        payment_method=payment_method,
        paid_amount=Decimal(str(paid_amount)),
        status=Sale.Status.DRAFT,
        note=note,
        lane_name=lane_name,
        discount=discount,
        tax=tax,
    )

    subtotal = Decimal("0.00")

    for raw_item in items:
        product = Product.objects.select_for_update().get(pk=raw_item["product_id"], is_active=True)
        quantity = int(raw_item["quantity"])
        branch_stock = get_branch_stock(product, sale.branch) if sale.branch else None
        available_quantity = branch_stock.quantity if branch_stock is not None else product.quantity

        if quantity > available_quantity:
            raise ValidationError(f"Only {available_quantity} unit(s) left for {product.name}.")

        unit_price = Decimal(str(raw_item.get("unit_price") or product.selling_price))
        cost_price = Decimal(str(product.cost_price))
        line_total = unit_price * quantity
        profit = (unit_price - cost_price) * quantity

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            cost_price=cost_price,
            line_total=line_total,
            profit=profit,
        )

        before_quantity = available_quantity
        after_quantity = available_quantity - quantity
        if branch_stock is not None:
            branch_stock.quantity = after_quantity
            branch_stock.save(update_fields=["quantity", "updated_at"])
            apply_global_delta(product, -quantity)
        else:
            product.quantity = after_quantity
            product.save(update_fields=["quantity", "updated_at"])

        InventoryLog.objects.create(
            product=product,
            branch=sale.branch,
            quantity=quantity,
            action=InventoryLog.Action.REMOVE,
            source=InventoryLog.Source.SALE,
            reason="POS sale",
            reference=sale.receipt_number,
            before_quantity=before_quantity,
            after_quantity=after_quantity,
            created_by=cashier,
        )

        subtotal += line_total

    total = subtotal - discount - redeemed_amount + tax
    if total < 0:
        total = Decimal("0.00")
    if sale.paid_amount < total:
        raise ValidationError("Paid amount cannot be less than total.")

    sale.subtotal = subtotal
    sale.total = total
    sale.status = Sale.Status.COMPLETED
    points_awarded = 0
    if customer:
        points_awarded = int(total // Decimal("1000.00")) * business_settings.loyalty_points_per_1000
        customer.total_spent += total
        customer.loyalty_points = max(customer.loyalty_points - redeemed_points, 0) + points_awarded
        customer.save(update_fields=["total_spent", "loyalty_points", "updated_at"])

    sale.loyalty_points_awarded = points_awarded
    sale.save(update_fields=["subtotal", "total", "status", "loyalty_points_awarded", "updated_at"])

    log_activity(
        user=cashier,
        module=ActivityLog.Module.SALES,
        action="sale_completed",
        description=f"{cashier.username} completed sale {sale.receipt_number}",
        entity_type="sale",
        entity_id=sale.pk,
        metadata={
            "lane_name": lane_name,
            "total": str(total),
            "customer_phone": customer_phone,
            "redeemed_points": redeemed_points,
            "points_awarded": points_awarded,
        },
    )
    return sale
