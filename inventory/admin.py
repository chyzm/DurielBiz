from django.contrib import admin

from accounts.admin_mixins import TenantModelAdmin
from .models import InventoryLog


@admin.register(InventoryLog)
class InventoryLogAdmin(TenantModelAdmin):
    list_display = ("product", "quantity", "action", "source", "reason", "created_by", "created_at")
    list_filter = ("business", "action", "source", "created_at")
    search_fields = ("product__name", "reason", "reference")
