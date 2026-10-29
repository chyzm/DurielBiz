from django.contrib import admin

from .tenancy import TenantOwnedModel


class TenantModelAdmin(admin.ModelAdmin):
    """Scope Django admin querysets and related fields to a business tenant."""

    def get_queryset(self, request):
        queryset = self.model._base_manager.all()
        if request.user.is_superuser:
            return queryset
        business_id = getattr(request.user, "business_id", None)
        if not business_id:
            return queryset.none()
        return queryset.filter(business_id=business_id)

    def save_model(self, request, obj, form, change):
        if not obj.business_id and not request.user.is_superuser:
            obj.business_id = request.user.business_id
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        related_model = db_field.remote_field.model
        if isinstance(related_model, type) and issubclass(related_model, TenantOwnedModel):
            queryset = related_model._base_manager.all()
            if not request.user.is_superuser:
                business_id = getattr(request.user, "business_id", None)
                queryset = queryset.filter(business_id=business_id) if business_id else queryset.none()
            kwargs["queryset"] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class TenantTabularInline(admin.TabularInline):
    """Tenant-aware queryset for models shown through an admin inline."""

    def get_queryset(self, request):
        queryset = self.model._base_manager.all()
        if request.user.is_superuser:
            return queryset
        business_id = getattr(request.user, "business_id", None)
        if not business_id:
            return queryset.none()
        return queryset.filter(business_id=business_id)
