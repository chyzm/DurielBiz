from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        INVENTORY = "inventory", "Inventory Officer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CASHIER)
    phone_number = models.CharField(max_length=20, blank=True)
    branch = models.ForeignKey(
        "reports.Branch",
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class ActivityLog(models.Model):
    class Module(models.TextChoices):
        AUTH = "auth", "Authentication"
        SALES = "sales", "Sales"
        INVENTORY = "inventory", "Inventory"
        PRODUCTS = "products", "Products"
        PURCHASES = "purchases", "Purchases"
        USERS = "users", "Users"
        SETTINGS = "settings", "Settings"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    module = models.CharField(max_length=20, choices=Module.choices)
    action = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100, blank=True)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_module_display()} - {self.action}"
