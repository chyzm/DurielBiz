import os

from django.conf import settings
from django.shortcuts import redirect

ALLOWED_PATH_PREFIXES = ("/licensing/", "/static/")


class LicenseGateMiddleware:
    """Locks the desktop app down to the activation screen once the trial has
    expired and no valid license is installed. Inert everywhere else (cloud
    deployment, local dev) so it can't accidentally block the SaaS dashboard."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if os.getenv("DURIELBIZ_DESKTOP") != "1" or not settings.LICENSE_MASTER_KEY_HASH:
            return self.get_response(request)
        if request.path.startswith(ALLOWED_PATH_PREFIXES):
            return self.get_response(request)

        from .services import get_license_status

        status = get_license_status()
        if status["licensed"] or status["trial_active"]:
            return self.get_response(request)

        return redirect("licensing:activate")
