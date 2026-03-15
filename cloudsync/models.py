import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def generate_sync_token():
    return secrets.token_urlsafe(32)


class Business(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_businesses",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class BusinessMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        VIEWER = "viewer", "Viewer"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business_memberships")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "business")]
        ordering = ["business__name", "user__username"]

    def __str__(self):
        return f"{self.user} @ {self.business}"


class SyncCredential(models.Model):
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="sync_credential")
    token = models.CharField(max_length=120, unique=True, default=generate_sync_token)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sync credential for {self.business}"


class RemoteBranch(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="branches")
    external_id = models.PositiveIntegerField(null=True, blank=True)
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("business", "code")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class RemoteSale(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="sales")
    branch = models.ForeignKey(RemoteBranch, on_delete=models.CASCADE, related_name="sales", null=True, blank=True)
    external_id = models.PositiveIntegerField()
    receipt_number = models.CharField(max_length=40)
    cashier_name = models.CharField(max_length=150)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    lane_name = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=20, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    redeemed_points = models.PositiveIntegerField(default=0)
    redeemed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at_remote = models.DateTimeField()
    updated_at_remote = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("business", "branch", "external_id")]
        ordering = ["-created_at_remote"]

    def __str__(self):
        return self.receipt_number


class RemoteSaleItem(models.Model):
    sale = models.ForeignKey(RemoteSale, on_delete=models.CASCADE, related_name="items")
    line_index = models.PositiveIntegerField()
    product_name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=120, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = [("sale", "line_index")]
        ordering = ["line_index"]


class RemotePurchase(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="purchases")
    branch = models.ForeignKey(RemoteBranch, on_delete=models.CASCADE, related_name="purchases", null=True, blank=True)
    external_id = models.PositiveIntegerField()
    invoice_no = models.CharField(max_length=100)
    supplier_name = models.CharField(max_length=255, blank=True)
    created_by_name = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    received_at_remote = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("business", "branch", "external_id")]
        ordering = ["-received_at_remote"]


class RemotePurchaseItem(models.Model):
    purchase = models.ForeignKey(RemotePurchase, on_delete=models.CASCADE, related_name="items")
    line_index = models.PositiveIntegerField()
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("purchase", "line_index")]
        ordering = ["line_index"]


class RemoteInventoryLog(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="inventory_logs")
    branch = models.ForeignKey(RemoteBranch, on_delete=models.CASCADE, related_name="inventory_logs", null=True, blank=True)
    external_id = models.PositiveIntegerField()
    product_name = models.CharField(max_length=255)
    quantity = models.IntegerField(default=0)
    action = models.CharField(max_length=20)
    source = models.CharField(max_length=20, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    before_quantity = models.IntegerField(default=0)
    after_quantity = models.IntegerField(default=0)
    created_by_name = models.CharField(max_length=150, blank=True)
    created_at_remote = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("business", "branch", "external_id")]
        ordering = ["-created_at_remote"]


class SyncEvent(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="sync_events")
    status = models.CharField(max_length=20, choices=Status.choices)
    message = models.CharField(max_length=255, blank=True)
    payload_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
