import json
import os
import re
from urllib import error, request as urllib_request
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from notifications.services import expiring_products_queryset, low_stock_products_queryset
from inventory.models import InventoryLog
from purchases.models import Purchase
from sales.models import Sale, SaleItem

from .models import Branch, BusinessSettings

SYNC_LOCK_FILENAME = "cloud_sync.lock"
SYNC_LOCK_STALE_SECONDS = 15 * 60


def user_identity(user):
    if user is None:
        return ""
    return user.email or user.get_full_name() or user.username


def dashboard_metrics(*, branch=None):
    today = timezone.localdate()
    sales_filter = {"status": Sale.Status.COMPLETED}
    if branch is not None:
        sales_filter["branch"] = branch

    sales_today = Sale.objects.filter(created_at__date=today, **sales_filter)

    revenue_today = sales_today.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    profit_today = (
        SaleItem.objects.filter(sale__in=sales_today).aggregate(total=Sum("profit"))["total"] or Decimal("0.00")
    )
    sales_count = sales_today.count()

    top_products_queryset = SaleItem.objects.filter(sale__created_at__date=today, sale__status=Sale.Status.COMPLETED)
    if branch is not None:
        top_products_queryset = top_products_queryset.filter(sale__branch=branch)
    top_products = (
        top_products_queryset
        .values("product__name")
        .annotate(quantity_sold=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-quantity_sold")
    )

    last_week_queryset = Sale.objects.filter(status=Sale.Status.COMPLETED, created_at__date__gte=today - timedelta(days=6))
    if branch is not None:
        last_week_queryset = last_week_queryset.filter(branch=branch)

    last_week = (
        last_week_queryset
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total"), count=Count("id"))
        .order_by("day")
    )

    expiring_products = expiring_products_queryset()
    if branch is not None:
        expiring_products = expiring_products.filter(branch_stocks__branch=branch).distinct()

    return {
        "revenue_today": revenue_today,
        "profit_today": profit_today,
        "sales_count": sales_count,
        "top_products": top_products,
        "low_stock": low_stock_products_queryset(branch=branch),
        "expiring_products": expiring_products,
        "selected_branch_name": branch.name if branch else "All Branches",
        "sales_chart": {
            "labels": [item["day"].strftime("%d %b") for item in last_week],
            "values": [float(item["total"] or 0) for item in last_week],
        },
    }


def current_branch():
    return BusinessSettings.get_solo().default_branch


def sync_export_payload(*, since=None, branch=None):
    settings_obj = BusinessSettings.get_solo()
    since_dt = parse_datetime(since) if isinstance(since, str) else since
    if since_dt is None:
        since_dt = timezone.now() - timedelta(days=7)

    sales = (
        Sale.objects.filter(status=Sale.Status.COMPLETED, updated_at__gte=since_dt)
        .select_related("branch", "cashier", "customer")
        .prefetch_related("items__product")
        .order_by("-updated_at")
    )
    purchases = (
        Purchase.objects.filter(created_at__gte=since_dt)
        .select_related("branch", "supplier", "created_by")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    inventory_logs = (
        InventoryLog.objects.filter(created_at__gte=since_dt)
        .select_related("branch", "product", "created_by")
        .order_by("-created_at")
    )
    if branch is not None:
        sales = sales.filter(branch=branch)
        purchases = purchases.filter(branch=branch)
        inventory_logs = inventory_logs.filter(branch=branch)
        branches = Branch.objects.filter(pk=branch.pk).order_by("name")
    else:
        branches = Branch.objects.order_by("name")

    return {
        "generated_at": timezone.now().isoformat(),
        "business": {
            "name": settings_obj.business_name,
            "default_branch": settings_obj.default_branch.code if settings_obj.default_branch else "",
            "sync_dashboard_url": settings_obj.sync_dashboard_url,
        },
        "branches": [
            {
                "id": branch.pk,
                "name": branch.name,
                "code": branch.code,
                "address": branch.address,
                "phone": branch.phone,
                "is_active": branch.is_active,
            }
            for branch in branches
        ]
        if branches.exists() else [],
        "sales": [
            {
                "id": sale.pk,
                "receipt_number": sale.receipt_number,
                "branch": sale.branch.code if sale.branch else "",
                "cashier": user_identity(sale.cashier),
                "customer_name": sale.customer_name,
                "customer_phone": sale.customer_phone,
                "lane_name": sale.lane_name,
                "payment_method": sale.payment_method,
                "subtotal": str(sale.subtotal),
                "redeemed_points": sale.redeemed_points,
                "redeemed_amount": str(sale.redeemed_amount),
                "total": str(sale.total),
                "paid_amount": str(sale.paid_amount),
                "created_at": sale.created_at.isoformat(),
                "updated_at": sale.updated_at.isoformat(),
                "items": [
                    {
                        "product": item.product.name,
                        "barcode": item.product.barcode or "",
                        "quantity": item.quantity,
                        "unit_price": str(item.unit_price),
                        "cost_price": str(item.cost_price),
                        "line_total": str(item.line_total),
                        "profit": str(item.profit),
                    }
                    for item in sale.items.all()
                ],
            }
            for sale in sales[:200]
        ],
        "purchases": [
            {
                "id": purchase.pk,
                "invoice_no": purchase.invoice_no,
                "branch": purchase.branch.code if purchase.branch else "",
                "supplier": purchase.supplier.name,
                "received_at": purchase.received_at.isoformat(),
                "created_by": user_identity(purchase.created_by),
                "notes": purchase.notes,
                "items": [
                    {
                        "product": item.product.name,
                        "quantity": item.quantity,
                        "cost_price": str(item.cost_price),
                        "expiry_date": item.expiry_date.isoformat() if item.expiry_date else "",
                    }
                    for item in purchase.items.all()
                ],
            }
            for purchase in purchases[:200]
        ],
        "inventory_logs": [
            {
                "id": log.pk,
                "branch": log.branch.code if log.branch else "",
                "product": log.product.name,
                "quantity": log.quantity,
                "action": log.action,
                "source": log.source,
                "reason": log.reason,
                "reference": log.reference,
                "before_quantity": log.before_quantity,
                "after_quantity": log.after_quantity,
                "created_by": user_identity(log.created_by),
                "created_at": log.created_at.isoformat(),
            }
            for log in inventory_logs[:300]
        ],
    }


def push_sync_payload(*, endpoint_url, token, since=None):
    payload = sync_export_payload(since=since)
    request = urllib_request.Request(
        endpoint_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Sync-Token": token,
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {"ok": True}
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(format_sync_http_error(exc.code, details)) from exc
    except error.URLError as exc:
        raise ValueError(f"Sync failed: {exc.reason}") from exc


def perform_cloud_sync(*, settings_obj, since=None):
    response = push_sync_payload(
        endpoint_url=settings_obj.sync_dashboard_url,
        token=settings_obj.cloud_sync_token,
        since=since,
    )
    settings_obj.last_cloud_sync_at = timezone.now()
    settings_obj.save(update_fields=["last_cloud_sync_at", "updated_at"])
    return response


def cloud_sync_ready(settings_obj):
    return bool(
        settings_obj.cloud_sync_enabled
        and settings_obj.auto_sync_enabled
        and settings_obj.cloud_sync_token
        and settings_obj.sync_dashboard_url
    )


def cloud_sync_due(settings_obj, *, now=None):
    if not cloud_sync_ready(settings_obj):
        return False
    current_time = now or timezone.now()
    if settings_obj.last_cloud_sync_at is None:
        return True
    next_due_at = settings_obj.last_cloud_sync_at + timedelta(minutes=settings_obj.auto_sync_interval_minutes)
    return current_time >= next_due_at


def sync_lock_path():
    data_root = os.environ.get("DURIELBIZ_DATA_DIR")
    base_path = Path(data_root) if data_root else Path.cwd()
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / SYNC_LOCK_FILENAME


def acquire_sync_lock():
    lock_path = sync_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        file_descriptor = os.open(lock_path, flags)
    except FileExistsError:
        try:
            age_seconds = timezone.now().timestamp() - lock_path.stat().st_mtime
        except OSError:
            return None
        if age_seconds < SYNC_LOCK_STALE_SECONDS:
            return None
        try:
            lock_path.unlink()
        except OSError:
            return None
        try:
            file_descriptor = os.open(lock_path, flags)
        except FileExistsError:
            return None
    os.write(file_descriptor, str(os.getpid()).encode("utf-8"))
    return file_descriptor


def release_sync_lock(file_descriptor):
    lock_path = sync_lock_path()
    try:
        os.close(file_descriptor)
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass


def run_scheduled_cloud_sync(*, settings_obj=None):
    settings_obj = settings_obj or BusinessSettings.get_solo()
    lock_handle = acquire_sync_lock()
    if lock_handle is None:
        return {"ok": False, "message": "Another sync worker is already running."}
    try:
        if not cloud_sync_due(settings_obj):
            return {"ok": False, "message": "Cloud sync is not due yet."}
        try:
            response = perform_cloud_sync(settings_obj=settings_obj)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "message": f"Cloud sync failed unexpectedly: {exc}"}
        return {"ok": True, "message": "Cloud sync completed.", "response": response if isinstance(response, dict) else {}}
    finally:
        release_sync_lock(lock_handle)


def format_sync_http_error(status_code, response_text):
    body = (response_text or "").strip()
    if not body:
        return f"Sync failed with HTTP {status_code}."

    if body.lstrip().startswith("<"):
        title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
        if title:
            return f"Sync failed with HTTP {status_code}: {title}"
        return f"Sync failed with HTTP {status_code}. The cloud server returned an HTML error page."

    compact_body = re.sub(r"\s+", " ", body)
    if len(compact_body) > 240:
        compact_body = f"{compact_body[:237]}..."
    return compact_body
