import os

from django.db import transaction


def assign_desktop_pk(instance, using="default"):
    """Give offline-created rows a device-specific negative key range.

    Cloud-originated rows retain positive auto-increment keys; independently
    created desktop rows therefore do not collide with cloud-created records.
    """
    if os.getenv("DURIELBIZ_DESKTOP") != "1" or instance.pk is not None:
        return False
    device_id = os.getenv("DURIELBIZ_SYNC_DEVICE_ID", "")
    try:
        prefix = int(device_id.replace("-", "")[:10], 16)
    except (TypeError, ValueError):
        return False
    width = 1_000_000
    base = prefix * width
    model = type(instance)
    with transaction.atomic(using=using):
        pks = model._base_manager.using(using).filter(pk__lt=0, pk__gte=-(base + width)).values_list("pk", flat=True)
        used = [abs(pk) - base for pk in pks]
        counter = max(used, default=0) + 1
        if counter >= width:
            raise RuntimeError("This sync device has exhausted its local ID range.")
        instance.pk = -(base + counter)
        return True
