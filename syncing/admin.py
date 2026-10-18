from django.contrib import admin

from .models import SyncDevice


@admin.register(SyncDevice)
class SyncDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "is_active", "created_at", "last_seen_at")
    list_filter = ("is_active", "business")
    search_fields = ("name", "business__name", "business__slug")
    readonly_fields = ("id", "token_hash", "created_at", "last_seen_at")
