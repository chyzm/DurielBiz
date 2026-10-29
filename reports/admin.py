from django.contrib import admin

from accounts.admin_mixins import TenantModelAdmin
from .models import Branch, BusinessSettings


@admin.register(Branch)
class BranchAdmin(TenantModelAdmin):
    list_display = ("name", "code", "phone", "is_active", "updated_at")
    list_filter = ("business", "is_active")


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(TenantModelAdmin):
    list_display = (
        "business_name",
        "default_branch",
        "phone",
        "updated_at",
    )
