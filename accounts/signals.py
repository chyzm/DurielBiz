from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .activity import log_activity
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
        ip_address=request.META.get("REMOTE_ADDR"),
    )
