import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import User
from pos_system.pagination import paginate_queryset

from .forms import CloudSignupForm
from .models import Business, BusinessMembership, RemoteInventoryLog, SyncCredential
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
        messages.success(request, "Your cloud dashboard is ready. Next, connect your existing local POS from the sync settings page.")
        return redirect("cloudsync:settings")

    return render(request, "cloudsync/signup.html", {"form": form})


@business_required
def dashboard(request):
    business = request.cloud_business
    context = dashboard_metrics(business)
    context["business"] = business
    return render(request, "cloudsync/dashboard.html", context)


def filtered_sales(request, business):
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
    return sales, start_date, end_date, branch_code


@business_required
def sales_list(request):
    business = request.cloud_business
    sales, start_date, end_date, branch_code = filtered_sales(request, business)
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
def sales_export_csv(request):
    business = request.cloud_business
    sales, start_date, end_date, branch_code = filtered_sales(request, business)

    branch_label = branch_code or "all-branches"
    start_label = start_date or "all-dates"
    end_label = end_date or start_label
    filename = f"cloud-sales-{start_label}-to-{end_label}-{branch_label}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Receipt",
            "Date",
            "Branch",
            "Cashier",
            "Customer",
            "Phone",
            "Lane",
            "Payment Method",
            "Subtotal",
            "Redeemed Points",
            "Redeemed Amount",
            "Total",
            "Paid Amount",
            "Product",
            "Quantity",
            "Unit Price",
            "Line Total",
            "Profit",
        ]
    )
    for sale in sales.iterator():
        items = list(sale.items.all())
        if not items:
            writer.writerow(
                [
                    sale.receipt_number,
                    sale.created_at_remote.strftime("%Y-%m-%d %H:%M:%S"),
                    sale.branch.name if sale.branch_id else "",
                    sale.cashier_name,
                    sale.customer_name,
                    sale.customer_phone,
                    sale.lane_name,
                    sale.payment_method,
                    sale.subtotal,
                    sale.redeemed_points,
                    sale.redeemed_amount,
                    sale.total,
                    sale.paid_amount,
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        for item in items:
            writer.writerow(
                [
                    sale.receipt_number,
                    sale.created_at_remote.strftime("%Y-%m-%d %H:%M:%S"),
                    sale.branch.name if sale.branch_id else "",
                    sale.cashier_name,
                    sale.customer_name,
                    sale.customer_phone,
                    sale.lane_name,
                    sale.payment_method,
                    sale.subtotal,
                    sale.redeemed_points,
                    sale.redeemed_amount,
                    sale.total,
                    sale.paid_amount,
                    item.product_name,
                    item.quantity,
                    item.unit_price,
                    item.line_total,
                    item.profit,
                ]
            )
    return response


def filtered_inventory_logs(request, business):
    logs = business.inventory_logs.select_related("branch").order_by("-created_at_remote", "-id")
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    branch_code = request.GET.get("branch", "").strip()
    action = request.GET.get("action", "").strip()

    if start_date:
        logs = logs.filter(created_at_remote__date__gte=start_date)
    if end_date:
        logs = logs.filter(created_at_remote__date__lte=end_date)
    if branch_code:
        logs = logs.filter(branch__code=branch_code)
    if action:
        logs = logs.filter(action=action)

    return logs, start_date, end_date, branch_code, action


@business_required
def inventory_list(request):
    business = request.cloud_business
    logs, start_date, end_date, branch_code, action = filtered_inventory_logs(request, business)

    latest_snapshot = []
    seen_keys = set()
    for log in logs:
        key = (log.branch_id, log.product_name)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        latest_snapshot.append(log)
        if len(latest_snapshot) >= 20:
            break

    logs_page = paginate_queryset(request, logs, per_page=20)
    return render(
        request,
        "cloudsync/inventory.html",
        {
            "business": business,
            "logs": logs_page,
            "branches": business.branches.order_by("name"),
            "actions": business.inventory_logs.values_list("action", flat=True).distinct().order_by("action"),
            "selected_branch": branch_code,
            "selected_action": action,
            "start_date": start_date,
            "end_date": end_date,
            "latest_snapshot": latest_snapshot,
        },
    )


@business_required
def inventory_export_csv(request):
    business = request.cloud_business
    logs, start_date, end_date, branch_code, action = filtered_inventory_logs(request, business)

    branch_label = branch_code or "all-branches"
    action_label = action or "all-actions"
    start_label = start_date or "all-dates"
    end_label = end_date or start_label
    filename = f"cloud-inventory-{start_label}-to-{end_label}-{branch_label}-{action_label}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Date",
            "Branch",
            "Product",
            "Action",
            "Source",
            "Reason",
            "Movement Quantity",
            "Before Quantity",
            "After Quantity",
            "Created By",
            "Reference",
        ]
    )

    for log in logs.iterator():
        writer.writerow(
            [
                log.created_at_remote.strftime("%Y-%m-%d %H:%M:%S"),
                log.branch.name if log.branch_id else "",
                log.product_name,
                log.action,
                log.source,
                log.reason,
                log.quantity,
                log.before_quantity,
                log.after_quantity,
                log.created_by_name,
                log.reference,
            ]
        )

    return response


def filtered_purchases(request, business):
    purchases = business.purchases.select_related("branch").prefetch_related("items").order_by("-received_at_remote")
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    branch_code = request.GET.get("branch", "").strip()
    if start_date:
        purchases = purchases.filter(received_at_remote__date__gte=start_date)
    if end_date:
        purchases = purchases.filter(received_at_remote__date__lte=end_date)
    if branch_code:
        purchases = purchases.filter(branch__code=branch_code)
    return purchases, start_date, end_date, branch_code


@business_required
def purchase_list(request):
    business = request.cloud_business
    purchases, start_date, end_date, branch_code = filtered_purchases(request, business)
    purchases_page = paginate_queryset(request, purchases, per_page=20)
    return render(
        request,
        "cloudsync/purchases.html",
        {
            "business": business,
            "purchases": purchases_page,
            "branches": business.branches.order_by("name"),
            "start_date": start_date,
            "end_date": end_date,
            "selected_branch": branch_code,
        },
    )


@business_required
def purchase_export_csv(request):
    business = request.cloud_business
    purchases, start_date, end_date, branch_code = filtered_purchases(request, business)

    branch_label = branch_code or "all-branches"
    start_label = start_date or "all-dates"
    end_label = end_date or start_label
    filename = f"cloud-purchases-{start_label}-to-{end_label}-{branch_label}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Invoice No",
            "Date",
            "Branch",
            "Supplier",
            "Created By",
            "Notes",
            "Product",
            "Quantity",
            "Cost Price",
            "Expiry Date",
        ]
    )
    for purchase in purchases.iterator():
        items = list(purchase.items.all())
        if not items:
            writer.writerow(
                [
                    purchase.invoice_no,
                    purchase.received_at_remote.strftime("%Y-%m-%d %H:%M:%S"),
                    purchase.branch.name if purchase.branch_id else "",
                    purchase.supplier_name,
                    purchase.created_by_name,
                    purchase.notes,
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        for item in items:
            writer.writerow(
                [
                    purchase.invoice_no,
                    purchase.received_at_remote.strftime("%Y-%m-%d %H:%M:%S"),
                    purchase.branch.name if purchase.branch_id else "",
                    purchase.supplier_name,
                    purchase.created_by_name,
                    purchase.notes,
                    item.product_name,
                    item.quantity,
                    item.cost_price,
                    item.expiry_date or "",
                ]
            )
    return response


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
