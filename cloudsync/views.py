from functools import wraps

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import User

from .forms import CloudSignupForm
from .models import Business, BusinessMembership, SyncCredential
from .services import dashboard_metrics, ingest_payload, parse_request_json, user_business


def business_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        business = user_business(request.user)
        if business is None:
            messages.error(request, "No cloud business is linked to your account.")
            return redirect("accounts:home")
        request.cloud_business = business
        return view_func(request, *args, **kwargs)

    return login_required(_wrapped)


def signup(request):
    if request.user.is_authenticated and user_business(request.user):
        return redirect("cloudsync:dashboard")

    form = CloudSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.email = form.cleaned_data["email"]
        user.role = User.Role.ADMIN
        user.save()

        business = Business.objects.create(
            name=form.cleaned_data["business_name"],
            slug=form.cleaned_data["business_slug"],
            owner=user,
        )
        BusinessMembership.objects.create(user=user, business=business, role=BusinessMembership.Role.OWNER)
        SyncCredential.objects.create(business=business)

        auth_login(request, user)
        messages.success(request, "Your cloud dashboard is ready.")
        return redirect("cloudsync:dashboard")

    return render(request, "cloudsync/signup.html", {"form": form})


@business_required
def dashboard(request):
    business = request.cloud_business
    context = dashboard_metrics(business)
    context["business"] = business
    return render(request, "cloudsync/dashboard.html", context)


@business_required
def sales_list(request):
    business = request.cloud_business
    sales = business.sales.select_related("branch").prefetch_related("items").order_by("-created_at_remote")
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    branch_code = request.GET.get("branch", "").strip()
    if start_date:
        sales = sales.filter(created_at_remote__date__gte=start_date)
    if end_date:
        sales = sales.filter(created_at_remote__date__lte=end_date)
    if branch_code:
        sales = sales.filter(branch__code=branch_code)
    return render(
        request,
        "cloudsync/sales.html",
        {
            "business": business,
            "sales": sales[:100],
            "branches": business.branches.order_by("name"),
            "start_date": start_date,
            "end_date": end_date,
            "selected_branch": branch_code,
        },
    )


@business_required
def branch_list(request):
    business = request.cloud_business
    return render(
        request,
        "cloudsync/branches.html",
        {
            "business": business,
            "branches": business.branches.order_by("name"),
        },
    )


@business_required
def settings_view(request):
    business = request.cloud_business
    credential, _ = SyncCredential.objects.get_or_create(business=business)
    ingest_url = request.build_absolute_uri(reverse("cloudsync:ingest-api"))
    return render(
        request,
        "cloudsync/settings.html",
        {"business": business, "credential": credential, "ingest_url": ingest_url},
    )


@business_required
@require_POST
def rotate_token(request):
    business = request.cloud_business
    credential, _ = SyncCredential.objects.get_or_create(business=business)
    credential.token = credential.__class__._meta.get_field("token").default()
    credential.save(update_fields=["token", "updated_at"])
    messages.success(request, "Sync token rotated successfully.")
    return redirect("cloudsync:settings")


@csrf_exempt
@require_POST
def ingest_api(request):
    token = request.headers.get("X-Sync-Token") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return HttpResponseForbidden("Missing sync token.")

    credential = SyncCredential.objects.select_related("business").filter(token=token, is_active=True).first()
    if credential is None:
        return HttpResponseForbidden("Invalid sync token.")

    try:
        payload = parse_request_json(request)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    summary = ingest_payload(credential=credential, payload=payload)
    return JsonResponse({"ok": True, "summary": summary, "business": credential.business.slug})
