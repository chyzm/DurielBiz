from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import SyncChange
from .protocol import model_for_label, serialize_object
from .state import sync_events_enabled


def _record(instance, operation):
    if not sync_events_enabled() or instance._meta.app_label == "syncing":
        return
    if model_for_label(instance._meta.label_lower) is None:
        return
    business_id = getattr(instance, "business_id", None)
    if not business_id:
        return
    payload = serialize_object(instance)
    SyncChange.objects.using(instance._state.db or "default").create(
        business_id=business_id,
        model_label=instance._meta.label_lower,
        object_pk=instance.pk,
        operation=operation,
        payload=payload,
    )


@receiver(post_save, dispatch_uid="syncing.capture_tenant_save")
def capture_tenant_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _record(instance, SyncChange.Operation.UPSERT)


@receiver(post_delete, dispatch_uid="syncing.capture_tenant_delete")
def capture_tenant_delete(sender, instance, **kwargs):
    _record(instance, SyncChange.Operation.DELETE)
