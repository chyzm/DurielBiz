from django.db import models
from accounts.tenancy import TenantOwnedModel


class Supplier(TenantOwnedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["business", "name"], name="uniq_supplier_name_business")]

    def __str__(self) -> str:
        return self.name
