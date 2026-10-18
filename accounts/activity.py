from .models import ActivityLog
from .tenancy import get_current_business_id


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_activity(*, user=None, module, action, description, entity_type="", entity_id=None, metadata=None, ip_address=None):
    user = user if getattr(user, "is_authenticated", False) else None
    business_id = getattr(user, "business_id", None) or get_current_business_id()
    # Anonymous events (such as failed login attempts) have no safe tenant to
    # attach to. Do not let global authentication events break the request.
    if business_id is None:
        return None
    ActivityLog.objects.create(
        user=user,
        business_id=business_id,
        module=module,
        action=action,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
        ip_address=ip_address,
    )
