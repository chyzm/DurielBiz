from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ActivityLog, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("POS Access", {"fields": ("role", "phone_number")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "module", "action", "description")
    list_filter = ("module", "created_at")
    search_fields = ("description", "action", "user__username")
