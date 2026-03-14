from django.contrib import admin

from .models import Branch, BusinessSettings


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "phone", "is_active", "updated_at")
    list_filter = ("is_active",)


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "default_branch",
        "phone",
        "cloud_sync_enabled",
        "auto_sync_enabled",
        "last_cloud_sync_at",
        "updated_at",
    )
