from django.contrib import admin

from accounts.admin_mixins import TenantModelAdmin, TenantTabularInline
from .models import Customer, Sale, SaleFinancialEntry, SaleItem


class SaleItemInline(TenantTabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "line_total", "profit")
    can_delete = False


@admin.register(Sale)
class SaleAdmin(TenantModelAdmin):
    list_display = ("receipt_number", "cashier", "customer_name", "lane_name", "total", "payment_method", "status", "business", "created_at")
    list_filter = ("business", "payment_method", "status", "created_at")
    search_fields = ("customer_name", "cashier__username")
    inlines = [SaleItemInline]


@admin.register(Customer)
class CustomerAdmin(TenantModelAdmin):
    list_display = ("name", "phone", "loyalty_points", "total_spent", "business", "updated_at")
    list_filter = ("business",)
    search_fields = ("name", "phone", "email")


@admin.register(SaleFinancialEntry)
class SaleFinancialEntryAdmin(TenantModelAdmin):
    list_display = ("sale", "kind", "status", "payment_method", "amount", "recorded_by", "created_at")
    list_filter = ("business", "kind", "status", "payment_method", "created_at")
    search_fields = ("sale__id", "reference", "reason")
    readonly_fields = tuple(field.name for field in SaleFinancialEntry._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
