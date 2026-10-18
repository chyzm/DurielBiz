from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
import logging

from .activity import get_client_ip, log_activity
from .models import ActivityLog, SuperadminActivityLog
from .tenancy import set_current_business_id

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    try:
        if user.is_superuser:
            SuperadminActivityLog.objects.create(
                user=user,
                business_id=user.business_id,
                action="superadmin_login",
                description=f"{user.username} logged in to the superadmin account",
                ip_address=get_client_ip(request) if request else None,
            )
            return
        # AuthenticationMiddleware initially establishes an empty tenant context for
        # anonymous requests. Switch to the authenticated user's tenant immediately.
        set_current_business_id(user.business_id)
        log_activity(
            user=user,
            module=ActivityLog.Module.AUTH,
            action="login",
            description=f"{user.username} logged in",
            entity_type="user",
            entity_id=user.pk,
            ip_address=get_client_ip(request) if request else None,
        )
    except Exception:
        # An audit-table outage must not turn valid credentials into a failed login.
        logger.exception("Could not record successful login activity for user %s", user.pk)


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    username = credentials.get("username", "unknown")
    try:
        log_activity(
            user=None,
            module=ActivityLog.Module.AUTH,
            action="login_failed",
            description=f"Failed login attempt for username '{username}'",
            entity_type="user",
            ip_address=get_client_ip(request) if request else None,
            metadata={"username": username},
        )
    except Exception:
        logger.exception("Could not record failed login activity")
