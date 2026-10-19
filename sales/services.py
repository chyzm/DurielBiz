from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import get_user_branch
from inventory.models import InventoryLog
from products.models import Product
from products.stock import apply_global_delta, branch_quantity, get_branch_stock
from reports.models import BusinessSettings

from .models import Customer, Sale, SaleFinancialEntry, SaleItem


class DuplicateCheckout(Exception):
    def __init__(self, sale_id):
        self.sale_id = sale_id


def _normalize_cart(items):
    if not isinstance(items, list) or not items or len(items) > 100:
        raise ValidationError("Cart must contain between 1 and 100 items.")
    normalized = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("Cart items are invalid.")
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("Cart items are invalid.") from exc
        if (
            product_id <= 0
            or str(product_id) != str(item["product_id"])
            or quantity <= 0
            or str(quantity) != str(item["quantity"])
        ):
            raise ValidationError("Cart quantities must be whole numbers greater than zero.")
        if product_id in seen:
            raise ValidationError("Each product may only appear once in the cart.")
        seen.add(product_id)
        normalized.append({"product_id": product_id, "quantity": quantity})
    return normalized


def _money_amount(value, label):
    try:
        amount = Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValidationError(f"{label} amount is invalid.") from exc
    if not amount.is_finite() or amount < 0:
        raise ValidationError(f"{label} amount must be a non-negative amount.")
    try:
        cents = amount.quantize(Decimal("0.01"))
    except ArithmeticError as exc:
        raise ValidationError(f"{label} amount is invalid.") from exc
    if cents != amount:
        raise ValidationError(f"{label} amount cannot contain fractions of a cent.")
    return cents


def _validate_discount(*, cashier, discount, subtotal):
    discount = _money_amount(discount or 0, "Discount")
    if not discount.is_finite() or discount < 0 or discount > subtotal:
        raise ValidationError("Discount must be between zero and the sale subtotal.")
    if discount and getattr(cashier, "role", None) not in {User.Role.ADMIN, User.Role.MANAGER}:
        raise ValidationError("Only an admin or manager may apply a sales discount.")
    return discount


def _compute_tax(subtotal, discount, business_settings):
    taxable_base = max(subtotal - discount, Decimal("0.00"))
    if not business_settings.vat_enabled:
        return Decimal("0.00")
    return (taxable_base * business_settings.vat_rate_percent / Decimal("100")).quantize(Decimal("0.01"))


def compute_sale_preview(
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
):
    """Validate a would-be sale and return an unsaved preview object with the same
    shape sales/_receipt_content.html expects, without writing anything to the database."""
    business_settings = BusinessSettings.get_solo()
    sale_branch = get_user_branch(cashier) or business_settings.default_branch
    customer = Customer.objects.filter(phone=customer_phone).first() if customer_phone else None

    redeemed_points = int(redeemed_points or 0)
    if redeemed_points and not customer:
        raise ValidationError("Redeeming points requires a saved customer phone number.")
    if customer and redeemed_points > customer.loyalty_points:
        raise ValidationError("Customer does not have enough loyalty points.")
    redeemed_amount = Decimal(redeemed_points) * business_settings.loyalty_cash_value_per_point

    items = _normalize_cart(items)
    subtotal = Decimal("0.00")
    preview_items = []
    for raw_item in items:
        product = Product.objects.get(pk=raw_item["product_id"], is_active=True)
        quantity = int(raw_item["quantity"])
        available_quantity = branch_quantity(product, sale_branch)
        if quantity > available_quantity:
            raise ValidationError(f"Only {available_quantity} unit(s) left for {product.name}.")

        unit_price = Decimal(str(product.selling_price))
        line_total = unit_price * quantity
        subtotal += line_total
        preview_items.append(SimpleNamespace(product=product, quantity=quantity, unit_price=unit_price, line_total=line_total))

    discount = _validate_discount(cashier=cashier, discount=discount, subtotal=subtotal)
    tax = _compute_tax(subtotal, discount, business_settings)
    total = max(subtotal - discount - redeemed_amount + tax, Decimal("0.00"))
    paid_amount = _money_amount(paid_amount, "Payment")
    if paid_amount < total:
        raise ValidationError("Paid amount cannot be less than total.")

    return SimpleNamespace(
        receipt_number="PREVIEW",
        status="draft",
        cashier=cashier,
        branch=sale_branch,
        created_at=timezone.now(),
        lane_name=lane_name,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer=customer,
        items=preview_items,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        redeemed_points=redeemed_points,
        redeemed_amount=redeemed_amount,
        total=total,
        paid_amount=paid_amount,
        change_due=max(paid_amount - total, Decimal("0.00")),
        loyalty_points_awarded=0,
        note=note,
    )


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
    tax=None,
    tenders=None,
    idempotency_key=None,
):
    if idempotency_key:
        previous_sale = Sale.objects.select_for_update().filter(
            checkout_idempotency_key=idempotency_key
        ).first()
        if previous_sale:
            if previous_sale.cashier_id != cashier.pk or previous_sale.business_id != cashier.business_id:
                raise ValidationError("This checkout request key has already been used.")
            return previous_sale

    customer = None
    business_settings = BusinessSettings.get_solo()
    sale_branch = get_user_branch(cashier) or business_settings.default_branch
    items = _normalize_cart(items)
    if customer_phone:
        customer, created = Customer.objects.select_for_update().get_or_create(
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

    # Load and lock products in a stable order to reduce deadlocks when two tills
    # submit carts containing the same products in different orders.
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=sorted(item["product_id"] for item in items), is_active=True
        ).order_by("pk")
    }
    if len(products) != len(items):
        raise Product.DoesNotExist
    subtotal = sum(
        (Decimal(str(products[item["product_id"]].selling_price)) * item["quantity"] for item in items),
        Decimal("0.00"),
    )
    discount = _validate_discount(cashier=cashier, discount=discount, subtotal=subtotal)

    paid_amount = _money_amount(paid_amount, "Payment")
    if payment_method not in Sale.PaymentMethod.values:
        raise ValidationError("Payment method is invalid.")
    if payment_method == Sale.PaymentMethod.MIXED:
        if not isinstance(tenders, (list, tuple)) or len(tenders) < 2:
            raise ValidationError("Mixed payment requires at least two individual tenders.")
        normalized_tenders = []
        for tender in tenders:
            method = tender.get("payment_method")
            if method not in {Sale.PaymentMethod.CASH, Sale.PaymentMethod.CARD, Sale.PaymentMethod.TRANSFER}:
                raise ValidationError("A mixed tender must use cash, card, or transfer.")
            amount = _money_amount(tender.get("tendered_amount"), "Tender")
            if amount <= 0:
                raise ValidationError("Each mixed tender must be greater than zero.")
            normalized_tenders.append((method, amount))
        if sum((amount for _, amount in normalized_tenders), Decimal("0.00")) != paid_amount:
            raise ValidationError("Mixed tender amounts must equal the paid amount.")
        if len(normalized_tenders) < 2:
            raise ValidationError("Mixed payment requires at least two individual tenders.")
    else:
        if tenders:
            raise ValidationError("Individual tenders are only accepted for a mixed payment.")
        normalized_tenders = [(payment_method, paid_amount)]

    try:
        with transaction.atomic():
            sale = Sale.objects.create(
                cashier=cashier,
                branch=sale_branch,
                customer=customer,
                customer_name=customer_name,
                customer_phone=customer_phone,
                redeemed_points=redeemed_points,
                redeemed_amount=redeemed_amount,
                payment_method=payment_method,
                paid_amount=paid_amount,
                status=Sale.Status.DRAFT,
                note=note,
                lane_name=lane_name,
                discount=discount,
                checkout_idempotency_key=idempotency_key,
            )
    except IntegrityError:
        if idempotency_key:
            existing = Sale._base_manager.filter(checkout_idempotency_key=idempotency_key).first()
            if existing and existing.cashier_id == cashier.pk and existing.business_id == cashier.business_id:
                # Roll back this transaction before returning the committed sale.
                raise DuplicateCheckout(existing.pk)
        raise

    subtotal = Decimal("0.00")

    for raw_item in items:
        product = products[raw_item["product_id"]]
        quantity = int(raw_item["quantity"])
        branch_stock = get_branch_stock(product, sale.branch) if sale.branch else None
        available_quantity = branch_stock.quantity if branch_stock is not None else product.quantity

        if quantity > available_quantity:
            raise ValidationError(f"Only {available_quantity} unit(s) left for {product.name}.")

        unit_price = Decimal(str(product.selling_price))
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

    # Tax is derived from server-owned prices and settings; never accept a client
    # supplied tax amount.
    tax = _compute_tax(subtotal, discount, business_settings)

    total = subtotal - discount - redeemed_amount + tax
    if total < 0:
        total = Decimal("0.00")
    if sale.paid_amount < total:
        raise ValidationError("Paid amount cannot be less than total.")

    sale.subtotal = subtotal
    sale.tax = tax
    sale.total = total
    sale.status = Sale.Status.COMPLETED
    points_awarded = 0
    if customer:
        points_awarded = int(total // Decimal("1000.00")) * business_settings.loyalty_points_per_1000
        customer.total_spent += total
        customer.loyalty_points = max(customer.loyalty_points - redeemed_points, 0) + points_awarded
        customer.save(update_fields=["total_spent", "loyalty_points", "updated_at"])

    sale.loyalty_points_awarded = points_awarded
    sale.save(update_fields=["subtotal", "tax", "total", "status", "loyalty_points_awarded", "updated_at"])
    if total > 0:
        non_cash_total = sum((amount for method, amount in normalized_tenders if method != Sale.PaymentMethod.CASH), Decimal("0.00"))
        cash_total = sum((amount for method, amount in normalized_tenders if method == Sale.PaymentMethod.CASH), Decimal("0.00"))
        if non_cash_total > total or cash_total < total - non_cash_total:
            raise ValidationError("Card and transfer tenders must fit within the sale total, and cash must cover any balance.")
        remaining = total
        ordered_tenders = sorted(normalized_tenders, key=lambda tender: tender[0] == Sale.PaymentMethod.CASH)
        for method, tendered in ordered_tenders:
            applied = tendered if method != Sale.PaymentMethod.CASH else min(remaining, tendered)
            change = tendered - applied
            if applied > 0:
                SaleFinancialEntry.objects.create(
                    sale=sale,
                    kind=SaleFinancialEntry.Kind.PAYMENT,
                    status=SaleFinancialEntry.Status.SETTLED,
                    payment_method=method,
                    amount=applied,
                    tendered_amount=tendered,
                    change_given=change,
                    reference=sale.receipt_number,
                    recorded_by=cashier,
                )
            remaining -= applied
        if remaining > 0:
            raise ValidationError("Tender amounts do not cover the sale total.")

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
            "payment_tenders": [
                {"method": method, "tendered_amount": str(amount)}
                for method, amount in normalized_tenders
            ],
            "customer_phone": customer_phone,
            "redeemed_points": redeemed_points,
            "points_awarded": points_awarded,
        },
    )
    return sale


@transaction.atomic
def void_sale(*, sale, voided_by, reason="", ip_address=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A void reason is required.")

    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != Sale.Status.COMPLETED:
        raise ValidationError("Only completed sales can be voided.")

    # Use the same Customer -> Product lock order as checkout to reduce deadlocks.
    customer = Customer.objects.select_for_update().get(pk=sale.customer_id) if sale.customer_id else None

    for item in sale.items.select_related("product").select_for_update(of=("product",)):
        product = item.product
        branch_stock = get_branch_stock(product, sale.branch) if sale.branch else None
        before_quantity = branch_stock.quantity if branch_stock is not None else product.quantity
        after_quantity = before_quantity + item.quantity

        if branch_stock is not None:
            branch_stock.quantity = after_quantity
            branch_stock.save(update_fields=["quantity", "updated_at"])
            apply_global_delta(product, item.quantity)
        else:
            product.quantity = after_quantity
            product.save(update_fields=["quantity", "updated_at"])

        InventoryLog.objects.create(
            product=product,
            branch=sale.branch,
            quantity=item.quantity,
            action=InventoryLog.Action.ADD,
            source=InventoryLog.Source.REFUND,
            reason=reason,
            reference=sale.receipt_number,
            before_quantity=before_quantity,
            after_quantity=after_quantity,
            created_by=voided_by,
        )

    if customer:
        customer.loyalty_points = max(customer.loyalty_points - sale.loyalty_points_awarded, 0) + sale.redeemed_points
        customer.total_spent = max(customer.total_spent - sale.total, Decimal("0.00"))
        customer.save(update_fields=["loyalty_points", "total_spent", "updated_at"])

    sale.status = Sale.Status.VOIDED
    sale.voided_by = voided_by
    sale.voided_at = timezone.now()
    sale.void_reason = reason
    sale.save(update_fields=["status", "voided_by", "voided_at", "void_reason", "updated_at"])
    if sale.total > 0:
        payments = list(sale.financial_entries.filter(kind=SaleFinancialEntry.Kind.PAYMENT))
        for payment in payments:
            SaleFinancialEntry.objects.create(
                sale=sale,
                kind=SaleFinancialEntry.Kind.REFUND,
                status=SaleFinancialEntry.Status.PENDING,
                payment_method=payment.payment_method,
                amount=payment.amount,
                tendered_amount=payment.amount,
                reference=payment.reference,
                reason=reason,
                recorded_by=voided_by,
            )

    log_activity(
        user=voided_by,
        module=ActivityLog.Module.SALES,
        action="sale_voided",
        description=f"{voided_by.username} voided sale {sale.receipt_number}",
        entity_type="sale",
        entity_id=sale.pk,
        metadata={"reason": reason, "total": str(sale.total), "items": sale.items.count()},
        ip_address=ip_address,
    )
    return sale


@transaction.atomic
def settle_sale_refund(*, entry, actor, reference=""):
    entry = SaleFinancialEntry.objects.select_for_update().select_related("sale").get(pk=entry.pk)
    if entry.kind != SaleFinancialEntry.Kind.REFUND or entry.status != SaleFinancialEntry.Status.PENDING:
        raise ValidationError("Only pending refunds can be marked as refunded.")
    if actor.business_id != entry.business_id or actor.role not in {User.Role.ADMIN, User.Role.MANAGER}:
        raise ValidationError("You are not allowed to settle this refund.")
    if actor.role == User.Role.MANAGER and actor.branch_id != entry.sale.branch_id:
        raise ValidationError("Managers can only settle refunds for their assigned branch.")
    reference = (reference or "").strip()
    if len(reference) > 120:
        raise ValidationError("Refund reference must be 120 characters or fewer.")
    entry.status = SaleFinancialEntry.Status.REFUNDED
    entry.resolved_by = actor
    entry.resolved_at = timezone.now()
    entry.resolution_reference = reference
    entry.save(update_fields=["status", "resolved_by", "resolved_at", "resolution_reference"])
    log_activity(
        user=actor,
        module=ActivityLog.Module.SALES,
        action="sale_refund_settled",
        description=f"{actor.username} recorded a refund for sale {entry.sale.receipt_number}",
        entity_type="sale_refund",
        entity_id=entry.pk,
        metadata={"amount": str(entry.amount), "sale_id": entry.sale_id, "reference": reference},
    )
    return entry
