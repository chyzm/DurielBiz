from django.contrib import admin

from accounts.admin_mixins import TenantModelAdmin
from .models import BranchStock, Category, Product


@admin.register(Category)
class CategoryAdmin(TenantModelAdmin):
    list_display = ("name", "slug", "business")
    list_filter = ("business",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(TenantModelAdmin):
    list_display = (
        "name",
        "barcode",
        "category",
        "quantity",
        "selling_price",
        "business",
        "expiry_date",
        "is_active",
    )
    list_filter = ("business", "category", "is_active")
    search_fields = ("name", "barcode")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(BranchStock)
class BranchStockAdmin(TenantModelAdmin):
    list_display = ("product", "branch", "quantity", "business", "updated_at")
    list_filter = ("business", "branch")
    search_fields = ("product__name", "branch__name")
