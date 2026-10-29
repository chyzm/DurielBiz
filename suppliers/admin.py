from django.contrib import admin

from accounts.admin_mixins import TenantModelAdmin
from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(TenantModelAdmin):
    list_display = ("name", "phone", "email", "business", "created_at")
    list_filter = ("business",)
    search_fields = ("name", "phone", "email")
