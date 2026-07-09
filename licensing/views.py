from django.contrib import messages
from django.shortcuts import redirect, render

from .fingerprint import get_hardware_fingerprint
from .services import activate_license, get_license_status


def activate_view(request):
    status = get_license_status()

    if request.method == "POST" and not status["licensed"]:
        try:
            activate_license(request.POST.get("activation_key", ""))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Activated. You can now sign in.")
            return redirect("accounts:login")
        status = get_license_status()

    return render(
        request,
        "licensing/activate.html",
        {"fingerprint": get_hardware_fingerprint(), "status": status},
    )
