from django.contrib import admin

from .models import InventoryLog


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "action", "source", "reason", "created_by", "created_at")
    list_filter = ("action", "source", "created_at")
    search_fields = ("product__name", "reason", "reference")
