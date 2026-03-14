from decimal import Decimal

from django.conf import settings
from django.db import models


class Purchase(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    @property
    def total_cost(self) -> Decimal:
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    def __str__(self) -> str:
        return self.invoice_no

    @property
    def inventory_reference(self) -> str:
        return f"purchase:{self.pk}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="purchase_items")
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    expiry_date = models.DateField(blank=True, null=True)

    @property
    def line_total(self) -> Decimal:
        return self.cost_price * self.quantity

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity}"
