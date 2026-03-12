from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from products.models import Product
from products.stock import branch_low_stock_queryset


def expiring_products_queryset(days=56):
    threshold = timezone.localdate() + timedelta(days=days)
    return Product.objects.filter(is_active=True, expiry_date__isnull=False, expiry_date__lte=threshold).order_by(
        "expiry_date"
    )


def low_stock_products_queryset(branch=None):
    if branch is not None:
        return branch_low_stock_queryset(branch).filter(is_active=True)
    return Product.objects.filter(is_active=True, quantity__lte=F("reorder_level")).order_by("quantity")
