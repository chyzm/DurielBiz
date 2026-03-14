from .models import ActivityLog


def log_activity(*, user=None, module, action, description, entity_type="", entity_id=None, metadata=None, ip_address=None):
    ActivityLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        module=module,
        action=action,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
        ip_address=ip_address,
    )
