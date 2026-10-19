import os

from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse
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
        if os.getenv("DURIELBIZ_DESKTOP") == "1":
            from accounts.models import Business

            slug = os.getenv("DURIELBIZ_SYNC_BUSINESS_SLUG", "").strip()
            business = Business._base_manager.filter(slug=slug).first() if slug else None
            if business is None:
                return HttpResponse("This desktop is not paired with an active cloud subscription.", status=403)
            if not business.is_active or business.subscription_expires_at is None or business.subscription_expired:
                return HttpResponse(
                    "The cloud subscription for this desktop is inactive or has expired. Contact DurielTech to renew it.",
                    status=403,
                )

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
