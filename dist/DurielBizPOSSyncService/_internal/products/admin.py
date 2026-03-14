from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "barcode",
        "category",
        "quantity",
        "selling_price",
        "expiry_date",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "barcode")
    prepopulated_fields = {"slug": ("name",)}
