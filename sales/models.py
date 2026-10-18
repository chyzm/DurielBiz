from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from accounts.tenancy import TenantOwnedModel


class Customer(TenantOwnedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    preferred_redeem_points = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["business", "phone"], name="uniq_customer_phone_business")]

    def __str__(self) -> str:
        return f"{self.name} ({self.phone})"


class Sale(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        VOIDED = "voided", "Voided"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        TRANSFER = "transfer", "Transfer"
        MIXED = "mixed", "Mixed"

    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    branch = models.ForeignKey("reports.Branch", on_delete=models.SET_NULL, related_name="sales", null=True, blank=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name="sales",
        blank=True,
        null=True,
    )
    customer_name = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    lane_name = models.CharField(max_length=20, default="checkout_a")
    redeemed_points = models.PositiveIntegerField(default=0)
    redeemed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    loyalty_points_awarded = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    note = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_sales",
        null=True,
        blank=True,
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def receipt_number(self) -> str:
        return f"SALE-{abs(self.pk):06d}" if self.pk else "DRAFT"

    @property
    def change_due(self) -> Decimal:
        return max(self.paid_amount - self.total, Decimal("0.00"))

    def __str__(self) -> str:
        return self.receipt_number


class SaleItem(TenantOwnedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity}"


class SaleFinancialEntry(TenantOwnedModel):
    """Append-only tender and refund ledger for a completed or voided sale."""

    class Kind(models.TextChoices):
        PAYMENT = "payment", "Payment"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        SETTLED = "settled", "Settled"
        PENDING = "pending", "Pending"
        REFUNDED = "refunded", "Refunded"

    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="financial_entries")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    status = models.CharField(max_length=12, choices=Status.choices)
    payment_method = models.CharField(max_length=20, choices=Sale.PaymentMethod.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tendered_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    change_given = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reference = models.CharField(max_length=120, blank=True)
    resolution_reference = models.CharField(max_length=120, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sale_financial_entries_recorded",
        null=True,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sale_financial_entries_resolved",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [models.Index(fields=["business", "kind", "status", "created_at"])]

    def save(self, *args, **kwargs):
        if self.amount <= 0:
            raise ValidationError("Financial ledger amounts must be greater than zero.")
        if self.kind not in self.Kind.values or self.payment_method not in Sale.PaymentMethod.values:
            raise ValidationError("Financial ledger type or payment method is invalid.")
        if self.kind == self.Kind.PAYMENT and self.status != self.Status.SETTLED:
            raise ValidationError("Recorded payments must be settled.")
        if self.kind == self.Kind.REFUND and self.status not in {self.Status.PENDING, self.Status.REFUNDED}:
            raise ValidationError("Refunds must be pending or marked as refunded.")
        if self.kind == self.Kind.REFUND and self.status == self.Status.REFUNDED and not (self.resolved_by_id and self.resolved_at):
            raise ValidationError("A completed refund must record who settled it and when.")
        if self.kind == self.Kind.REFUND and self.status == self.Status.PENDING and (self.resolved_by_id or self.resolved_at):
            raise ValidationError("A pending refund cannot have settlement details.")
        if self.pk:
            previous = type(self)._base_manager.filter(pk=self.pk).values(
                "sale_id", "kind", "payment_method", "amount", "tendered_amount", "change_given",
                "reference", "reason", "status", "resolution_reference",
                "resolved_by_id", "resolved_at",
            ).first()
            if previous and any(
                previous[field] != getattr(self, field)
                for field in ("sale_id", "kind", "payment_method", "amount", "tendered_amount", "change_given", "reference", "reason")
            ):
                raise ValidationError("Financial ledger entries are immutable; record a correcting event instead.")
            if previous and self.status != self.Status.REFUNDED:
                raise ValidationError("A settled payment or refund status cannot be reversed.")
            if previous and previous["kind"] != self.Kind.REFUND:
                raise ValidationError("Payment ledger entries cannot be modified.")
            if (
                previous
                and previous["status"] == self.Status.REFUNDED
                and (
                    self.resolution_reference != previous["resolution_reference"]
                    or self.resolved_by_id != previous["resolved_by_id"]
                    or self.resolved_at != previous["resolved_at"]
                )
            ):
                raise ValidationError("A settled refund reference cannot be changed.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount} for {self.sale.receipt_number}"


class SalesReconciliation(TenantOwnedModel):
    start_date = models.DateField()
    end_date = models.DateField()
    branch = models.ForeignKey("reports.Branch", on_delete=models.PROTECT, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales_reconciliations")
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SalesReconciliationLine(TenantOwnedModel):
    reconciliation = models.ForeignKey(SalesReconciliation, on_delete=models.CASCADE, related_name="lines")
    payment_method = models.CharField(max_length=20, choices=[
        (Sale.PaymentMethod.CASH, "Cash"),
        (Sale.PaymentMethod.CARD, "Card"),
        (Sale.PaymentMethod.TRANSFER, "Transfer"),
        (Sale.PaymentMethod.MIXED, "Mixed (legacy, unallocated)"),
    ])
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    counted_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["reconciliation", "payment_method"], name="uniq_reconcile_method")]

    @property
    def difference(self):
        return self.counted_amount - self.expected_amount


class SalesReconciliationEntry(TenantOwnedModel):
    line = models.ForeignKey(SalesReconciliationLine, on_delete=models.CASCADE, related_name="entries")
    financial_entry = models.OneToOneField(SaleFinancialEntry, on_delete=models.PROTECT, related_name="reconciliation_link")
