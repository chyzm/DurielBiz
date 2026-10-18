from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from .tenancy import reset_current_business_id, set_current_business_id


class TenantContextMiddleware:
    """Apply the authenticated user's business to tenant-aware model queries."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        business_id = user.business_id if user and user.is_authenticated else None
        token = set_current_business_id(business_id)
        try:
            return self.get_response(request)
        finally:
            reset_current_business_id(token)


class BusinessSubscriptionMiddleware:
    """End active sessions when a tenant subscription expires or is deactivated."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not user.is_superuser and user.business_id:
            business = user.business
            if not business.is_active or business.subscription_expired:
                expired = business.subscription_expired
                logout(request)
                if expired:
                    messages.error(request, "This business subscription has expired. Contact the administrator to renew it.")
                else:
                    messages.error(request, "This business account is inactive. Contact DurielTech to restore access.")
                return redirect("accounts:login")
        return self.get_response(request)
