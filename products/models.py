from decimal import Decimal

from django.db import models
from django.utils.text import slugify


def unique_slug_for_instance(instance, source_value, *, slug_field_name="slug", max_length=None):
    base_slug = slugify(source_value) or "item"
    if max_length:
        base_slug = base_slug[:max_length]
    slug = base_slug
    model_class = instance.__class__
    counter = 2

    while model_class.objects.filter(**{slug_field_name: slug}).exclude(pk=instance.pk).exists():
        suffix = f"-{counter}"
        if max_length:
            slug = f"{base_slug[: max_length - len(suffix)]}{suffix}"
        else:
            slug = f"{base_slug}{suffix}"
        counter += 1
    return slug


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        self.slug = unique_slug_for_instance(self, self.name, max_length=self._meta.get_field("slug").max_length)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        related_name="products",
        blank=True,
        null=True,
    )
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)
    expiry_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.slug = unique_slug_for_instance(self, self.name, max_length=self._meta.get_field("slug").max_length)
        super().save(*args, **kwargs)

    @property
    def margin(self) -> Decimal:
        return self.selling_price - self.cost_price

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level

    def __str__(self) -> str:
        return self.name


class BranchStock(models.Model):
    branch = models.ForeignKey("reports.Branch", on_delete=models.CASCADE, related_name="product_stocks")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="branch_stocks")
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["branch__name", "product__name"]
        unique_together = ("branch", "product")

    def __str__(self) -> str:
        return f"{self.product.name} @ {self.branch.name}"
