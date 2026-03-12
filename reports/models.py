from decimal import Decimal

from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class BusinessSettings(models.Model):
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
    loyalty_points_per_1000 = models.PositiveIntegerField(default=1)
    loyalty_cash_value_per_point = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    cloud_sync_enabled = models.BooleanField(default=False)
    cloud_sync_token = models.CharField(max_length=120, blank=True)
    sync_dashboard_url = models.URLField(blank=True)
    thermal_paper_width = models.CharField(
        max_length=10,
        choices=ThermalPaperWidth.choices,
        default=ThermalPaperWidth.MM80,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "business settings"

    def __str__(self) -> str:
        return self.business_name

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
