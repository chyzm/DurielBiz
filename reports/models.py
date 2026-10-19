from decimal import Decimal

from django.db import models
from accounts.tenancy import TenantOwnedModel


class Branch(TenantOwnedModel):
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=50)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["business", "code"], name="uniq_branch_code_business")]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class BusinessSettings(TenantOwnedModel):
    class ThermalPaperWidth(models.TextChoices):
        MM58 = "58mm", "58 mm"
        MM80 = "80mm", "80 mm"

    business_name = models.CharField(max_length=255, default="DurielBiz POS")
    default_branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="business_settings",
        blank=True,
        null=True,
    )
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    receipt_footer = models.CharField(max_length=255, blank=True, default="Thank you for your patronage.")
    vat_enabled = models.BooleanField(default=False)
    vat_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    loyalty_points_per_1000 = models.PositiveIntegerField(default=1)
    loyalty_cash_value_per_point = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    thermal_paper_width = models.CharField(
        max_length=10,
        choices=ThermalPaperWidth.choices,
        default=ThermalPaperWidth.MM80,
    )
    sync_referral_key_hash = models.CharField(max_length=256, blank=True, default="")
    sync_referral_key_updated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "business settings"
        constraints = [models.UniqueConstraint(fields=["business"], name="uniq_business_settings_tenant")]

    def __str__(self) -> str:
        return self.business_name

    @classmethod
    def get_solo(cls, business=None):
        filters = {"business": business} if business is not None else {}
        settings, _ = cls.objects.get_or_create(**filters)
        return settings
