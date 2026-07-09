from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .activity import get_client_ip, log_activity
from .models import ActivityLog


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    log_activity(
        user=user,
        module=ActivityLog.Module.AUTH,
        action="login",
        description=f"{user.username} logged in",
        entity_type="user",
        entity_id=user.pk,
        ip_address=get_client_ip(request) if request else None,
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    username = credentials.get("username", "unknown")
    log_activity(
        user=None,
        module=ActivityLog.Module.AUTH,
        action="login_failed",
        description=f"Failed login attempt for username '{username}'",
        entity_type="user",
        ip_address=get_client_ip(request) if request else None,
        metadata={"username": username},
    )
