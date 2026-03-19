from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class InvoicingIdleTimeoutMiddleware:
    session_key = "invoicing_last_activity"
    idle_timeout = timedelta(minutes=20)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/tools/") and request.user.is_authenticated and hasattr(request.user, "invoice_business"):
            last_activity_value = request.session.get(self.session_key)
            now = timezone.now()

            if last_activity_value:
                try:
                    last_activity = datetime.fromisoformat(last_activity_value)
                    if timezone.is_naive(last_activity):
                        last_activity = timezone.make_aware(last_activity, timezone.get_current_timezone())
                except ValueError:
                    last_activity = None
                if last_activity and now - last_activity > self.idle_timeout:
                    logout(request)
                    request.session.pop(self.session_key, None)
                    messages.warning(request, "Your Tools session expired after 20 minutes of inactivity.")
                    return redirect("invoicing:login")

            request.session[self.session_key] = now.isoformat()

        return self.get_response(request)
