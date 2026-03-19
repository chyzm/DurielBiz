from django.contrib import admin

from .models import Document, DocumentItem, InvoiceBusiness, ServiceItem, ToolSubscription


class DocumentItemInline(admin.TabularInline):
    model = DocumentItem
    extra = 0


@admin.register(InvoiceBusiness)
class InvoiceBusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "contact_email", "updated_at")
    search_fields = ("name", "slug", "owner__email", "owner__username")


@admin.register(ToolSubscription)
class ToolSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("business", "status", "expires_at", "monthly_price", "reminder_sent_at")
    list_filter = ("status",)
    search_fields = ("business__name", "business__owner__email")


@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "unit_price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "business__name")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "business", "document_type", "customer_name", "issue_date", "total")
    list_filter = ("document_type", "business")
    search_fields = ("number", "customer_name", "business__name")
    inlines = [DocumentItemInline]
