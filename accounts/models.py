from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .tenancy import TenantOwnedModel


class Business(models.Model):
    class SubscriptionPlan(models.TextChoices):
        MONTHLY = "monthly", "1 month"
        YEARLY = "yearly", "1 year"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    subscription_plan = models.CharField(max_length=12, choices=SubscriptionPlan.choices, default=SubscriptionPlan.YEARLY)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    reminder_7_days_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_1_day_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def subscription_expired(self):
        return self.subscription_expires_at is not None and timezone.now() >= self.subscription_expires_at


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        INVENTORY = "inventory", "Inventory Officer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CASHIER)
    phone_number = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(default=False)
    email_normalized = models.EmailField(blank=True, null=True, unique=True, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    branch = models.ForeignKey(
        "reports.Branch",
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["username"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.email_normalized = self.email or None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "email" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"email_normalized"}
        if self._state.adding and self.pk is None:
            from syncing.ids import assign_desktop_pk
            assign_desktop_pk(self, using=kwargs.get("using") or "default")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.business_id and self.branch_id:
            branch_business_id = (
                self.branch.__class__._base_manager.filter(pk=self.branch_id)
                .values_list("business_id", flat=True)
                .first()
            )
            if branch_business_id != self.business_id:
                raise ValidationError({"branch": "The selected branch belongs to another business."})

    def save(self, *args, **kwargs):
        if self.business_id and self.branch_id:
            self.clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class ActivityLog(TenantOwnedModel):
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


class SuperadminActivityLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="superadmin_activity_logs",
        null=True,
        blank=True,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.SET_NULL,
        related_name="superadmin_activity_logs",
        null=True,
        blank=True,
        db_index=True,
    )
    action = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "superadmin activity"
        verbose_name_plural = "superadmin activity"

    def __str__(self):
        return self.description


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
