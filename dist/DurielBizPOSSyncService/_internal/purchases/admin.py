from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "supplier", "received_at", "created_by")
    search_fields = ("invoice_no", "supplier__name")
    inlines = [PurchaseItemInline]
