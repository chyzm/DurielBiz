from django.contrib import admin

from accounts.admin_mixins import TenantModelAdmin, TenantTabularInline
from .models import Purchase, PurchaseItem


class PurchaseItemInline(TenantTabularInline):
    model = PurchaseItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "quantity", "cost_price", "expiry_date", "is_current")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


@admin.register(Purchase)
class PurchaseAdmin(TenantModelAdmin):
    list_display = ("invoice_no", "supplier", "received_at", "created_by")
    search_fields = ("invoice_no", "supplier__name")
    readonly_fields = ("business", "branch", "supplier", "invoice_no", "received_at", "created_by", "notes", "is_archived")
    inlines = [PurchaseItemInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False
