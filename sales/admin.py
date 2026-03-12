from django.contrib import admin

from .models import Customer, Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "line_total", "profit")
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "cashier", "customer_name", "lane_name", "total", "payment_method", "status", "created_at")
    list_filter = ("payment_method", "status", "created_at")
    search_fields = ("customer_name", "cashier__username")
    inlines = [SaleItemInline]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "loyalty_points", "total_spent", "updated_at")
    search_fields = ("name", "phone", "email")
