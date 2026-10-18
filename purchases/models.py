from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models
from accounts.tenancy import TenantOwnedModel


class Purchase(TenantOwnedModel):
    branch = models.ForeignKey("reports.Branch", on_delete=models.SET_NULL, related_name="purchases", null=True, blank=True)
    supplier = models.ForeignKey("suppliers.Supplier", on_delete=models.PROTECT, related_name="purchases")
    invoice_no = models.CharField(max_length=100)
    received_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="purchases",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    @property
    def total_cost(self) -> Decimal:
        return sum((item.line_total for item in self.items.filter(is_current=True)), Decimal("0.00"))

    def __str__(self) -> str:
        return self.invoice_no

    @property
    def inventory_reference(self) -> str:
        return f"purchase:{self.pk}"


class PurchaseItem(TenantOwnedModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="purchase_items")
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    expiry_date = models.DateField(blank=True, null=True)
    is_current = models.BooleanField(default=True)

    @property
    def line_total(self) -> Decimal:
        return self.cost_price * self.quantity

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity}"


class PurchaseCorrectionEvent(TenantOwnedModel):
    class Action(models.TextChoices):
        EDITED = "edited", "Edited"
        DELETED = "deleted", "Deleted"

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="corrections")
    action = models.CharField(max_length=12, choices=Action.choices)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
