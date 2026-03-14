from django.conf import settings
from django.db import models


class InventoryLog(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        PURCHASE = "purchase", "Purchase"
        SALE = "sale", "Sale"

    class Action(models.TextChoices):
        ADD = "add", "Add"
        REMOVE = "remove", "Remove"
        ADJUST = "adjust", "Adjust"

    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="inventory_logs")
    branch = models.ForeignKey("reports.Branch", on_delete=models.SET_NULL, related_name="inventory_logs", null=True, blank=True)
    quantity = models.IntegerField()
    action = models.CharField(max_length=10, choices=Action.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    reason = models.CharField(max_length=255)
    reference = models.CharField(max_length=120, blank=True)
    before_quantity = models.IntegerField(default=0)
    after_quantity = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="inventory_logs",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.product} - {self.action} ({self.quantity})"
