"""Request-local tenant context used by tenant-owned model managers."""

from contextvars import ContextVar
from django.db import models


_business_id = ContextVar("durielbiz_business_id", default=None)


def get_current_business_id():
    return _business_id.get()


def set_current_business_id(business_id):
    return _business_id.set(business_id)


def reset_current_business_id(token):
    _business_id.reset(token)


class TenantQuerySetMixin(models.QuerySet):
    def _tenant_filter(self):
        business_id = get_current_business_id()
        if business_id is None:
            return self.none()
        if business_id == "*":
            return self
        return self.filter(business_id=business_id)

    def all(self):
        return self._tenant_filter()

    def filter(self, *args, **kwargs):
        return super().filter(*args, **kwargs)

    def update(self, **kwargs):
        # The normal queryset already carries the current tenant filter. Prevent a
        # bulk update from moving those rows to another tenant in one operation.
        if "business" in kwargs or "business_id" in kwargs:
            raise ValueError("Tenant ownership cannot be changed with a bulk update.")
        return super().update(**kwargs)

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        business_id = get_current_business_id()
        objs = list(objs)
        if not objs:
            return super().bulk_create(
                objs,
                batch_size=batch_size,
                ignore_conflicts=ignore_conflicts,
                update_conflicts=update_conflicts,
                update_fields=update_fields,
                unique_fields=unique_fields,
            )
        if business_id is None:
            tenant_ids = {obj.business_id for obj in objs}
            if None in tenant_ids or len(tenant_ids) != 1:
                raise ValueError("Bulk creation without tenant context requires one explicit business.")
            business_id = tenant_ids.pop()
        for obj in objs:
            if business_id != "*" and obj.business_id not in (None, business_id):
                raise ValueError("Bulk-created records must belong to the current business.")
            for field in obj._meta.concrete_fields:
                related_model = getattr(getattr(field, "remote_field", None), "model", None)
                related_id = getattr(obj, field.attname, None)
                if field.name == "business" or not related_id or not related_model:
                    continue
                if any(candidate.name == "business" for candidate in related_model._meta.fields):
                    related_business_id = (
                        related_model._base_manager.filter(pk=related_id)
                        .values_list("business_id", flat=True)
                        .first()
                    )
                    if business_id != "*" and related_business_id != business_id:
                        raise ValueError("Bulk-created records must reference records from the same business.")
            if business_id != "*":
                obj.business_id = business_id
            elif not obj.business_id:
                raise ValueError("Global bulk creation requires every record to specify its business.")
        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )


class TenantManager(models.Manager.from_queryset(TenantQuerySetMixin)):
    def get_queryset(self):
        queryset = super().get_queryset()
        business_id = get_current_business_id()
        if business_id is None:
            return queryset.none()
        if business_id == "*":
            return queryset
        return queryset.filter(business_id=business_id)

    def create(self, **kwargs):
        if not kwargs.get("business_id") and not kwargs.get("business"):
            business_id = get_current_business_id()
            if not business_id:
                raise ValueError("A business must be selected when creating tenant data.")
            kwargs["business_id"] = business_id
        return super().create(**kwargs)


class TenantOwnedModel(models.Model):
    business = models.ForeignKey("accounts.Business", on_delete=models.CASCADE)

    objects = TenantManager()
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or "default"
        if self._state.adding and self.pk is None:
            from syncing.ids import assign_desktop_pk
            assign_desktop_pk(self, using=using)
        current_id = get_current_business_id()
        if not self.business_id:
            if not current_id:
                raise ValueError("A business must be selected when creating tenant data.")
            self.business_id = current_id
        elif current_id is not None and self.business_id != current_id:
            raise ValueError("Tenant data cannot be moved across businesses.")
        for field in self._meta.concrete_fields:
            related_model = getattr(getattr(field, "remote_field", None), "model", None)
            related_id = getattr(self, field.attname, None)
            if field.name == "business" or not related_id or not related_model:
                continue
            if any(candidate.name == "business" for candidate in related_model._meta.fields):
                related_business_id = (
                    related_model._base_manager.filter(pk=related_id)
                    .values_list("business_id", flat=True)
                    .first()
                )
                if related_business_id != self.business_id:
                    raise ValueError("Related records must belong to the same business.")
        return super().save(*args, **kwargs)
