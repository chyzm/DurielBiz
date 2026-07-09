from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        INVENTORY = "inventory", "Inventory Officer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CASHIER)
    phone_number = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(default=False)
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


class EmailOTP(models.Model):
    class Purpose(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Password Reset"

    email = models.EmailField()
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["email", "purpose", "code"])]
        ordering = ["-created_at"]

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() <= self.expires_at

    def __str__(self) -> str:
        return f"{self.email} - {self.get_purpose_display()}"
