from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError

from .models import SyncAppliedEvent, SyncChange
from .protocol import model_for_label
from .state import suppress_sync_events


class SyncConflict(Exception):
    pass


def _inventory_log_delta(values):
    try:
        return int(values.get("after_quantity", 0)) - int(values.get("before_quantity", 0))
    except (TypeError, ValueError, OverflowError) as exc:
        raise SyncConflict("An inventory event contained invalid stock values.") from exc


def _apply_inventory_delta(*, business, product_id, branch_id, delta, using):
    if not delta:
        return
    from products.models import BranchStock, Product

    product = Product._base_manager.using(using).select_for_update().filter(pk=product_id, business_id=business.pk).first()
    if product is None:
        raise SyncConflict("An inventory event referenced a missing product.")
    if branch_id:
        stock = BranchStock._base_manager.using(using).select_for_update().filter(
            product_id=product_id, branch_id=branch_id, business_id=business.pk
        ).first()
        if stock is None:
            raise SyncConflict("An inventory event arrived before its branch stock record.")
        if stock.quantity + delta < 0 or product.quantity + delta < 0:
            raise SyncConflict("This offline stock movement would make inventory negative; reconcile the stock conflict first.")
        stock.quantity += delta
        stock.save(using=using, update_fields=["quantity", "updated_at"])
    else:
        if product.quantity + delta < 0:
            raise SyncConflict("This offline stock movement would make inventory negative; reconcile the stock conflict first.")
    product.quantity += delta
    product.save(using=using, update_fields=["quantity", "updated_at"])


def apply_change(event, business, *, using="default", record_cloud_event=False, replay_inventory=True):
    model = model_for_label(event["model"])
    if model is None:
        raise SyncConflict("An unsupported model was included in the sync batch.")
    pk = int(event["pk"])
    payload = event.get("payload") or {}
    if payload.get("business_slug") != business.slug:
        raise SyncConflict("A sync change referenced a different business.")
    values = payload.get("values") or {}
    if model._meta.label_lower == "accounts.user" and values.get("is_superuser"):
        raise SyncConflict("A business sync device cannot create or promote a Django superuser.")
    current = model._base_manager.using(using).filter(pk=pk).first()
    if current is not None and getattr(current, "business_id", None) != business.pk:
        raise SyncConflict("A record key is already used by another business.")

    inventory_model = model._meta.label_lower == "inventory.inventorylog"
    incoming_values = ((event.get("payload") or {}).get("values") or {})
    if replay_inventory and inventory_model:
        old_values = {
            "before_quantity": current.before_quantity,
            "after_quantity": current.after_quantity,
        } if current is not None else {"before_quantity": 0, "after_quantity": 0}
        old_delta = _inventory_log_delta(old_values)
        new_delta = _inventory_log_delta(incoming_values) if event["operation"] == SyncChange.Operation.UPSERT else 0
        new_product_id = incoming_values.get("product_id", getattr(current, "product_id", None))
        new_branch_id = incoming_values.get("branch_id", getattr(current, "branch_id", None))
        old_product_id = getattr(current, "product_id", new_product_id)
        old_branch_id = getattr(current, "branch_id", new_branch_id)
        if current is not None and (old_product_id != new_product_id or old_branch_id != new_branch_id):
            _apply_inventory_delta(business=business, product_id=old_product_id, branch_id=old_branch_id, delta=-old_delta, using=using)
            _apply_inventory_delta(business=business, product_id=new_product_id, branch_id=new_branch_id, delta=new_delta, using=using)
        else:
            _apply_inventory_delta(
                business=business, product_id=new_product_id, branch_id=new_branch_id,
                delta=new_delta - old_delta, using=using,
            )

    with suppress_sync_events():
        if event["operation"] == SyncChange.Operation.DELETE:
            if current is not None:
                current.delete(using=using)
        elif event["operation"] == SyncChange.Operation.UPSERT:
            instance = current or model(pk=pk)
            instance.business_id = business.pk
            for field in model._meta.concrete_fields:
                if field.primary_key or field.name == "business" or field.attname not in values:
                    continue
                if replay_inventory and model._meta.label_lower in {"products.product", "products.branchstock"} and field.name == "quantity":
                    continue
                try:
                    setattr(instance, field.attname, field.to_python(values[field.attname]))
                except (TypeError, ValueError, ValidationError) as exc:
                    raise SyncConflict("A sync record contained an invalid field value.") from exc
            preserved_auto_fields = {
                field.attname: values[field.attname]
                for field in model._meta.concrete_fields
                if (getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False))
                and field.attname in values
            }
            try:
                instance.save(using=using)
                if preserved_auto_fields:
                    model._base_manager.using(using).filter(pk=pk).update(**preserved_auto_fields)
                    for name, value in preserved_auto_fields.items():
                        field = model._meta.get_field(name.removesuffix("_id")) if name.endswith("_id") else model._meta.get_field(name)
                        setattr(instance, name, field.to_python(value))
            except (ValueError, ValidationError, ObjectDoesNotExist, IntegrityError) as exc:
                raise SyncConflict("A sync record could not be applied because its references are invalid.") from exc
        else:
            raise SyncConflict("A sync operation was invalid.")

    SyncAppliedEvent.objects.using(using).get_or_create(event_id=event["event_id"])
    if record_cloud_event:
        SyncChange.objects.using(using).get_or_create(
            event_id=event["event_id"],
            defaults={
                "business_id": business.pk,
                "model_label": event["model"],
                "object_pk": pk,
                "operation": event["operation"],
                "payload": event.get("payload") or {},
            },
        )
