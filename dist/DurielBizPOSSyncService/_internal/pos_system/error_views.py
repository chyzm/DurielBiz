from django.shortcuts import render


def csrf_failure(request, reason=""):
    return render(
        request,
        "errors/csrf_failure.html",
        {"reason": reason},
        status=403,
    )


def server_error(request):
    return render(request, "errors/server_error.html", status=500)
