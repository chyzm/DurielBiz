import json

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    Business,
    BusinessMembership,
    RemoteBranch,
    RemoteInventoryLog,
    RemotePurchase,
    RemotePurchaseItem,
    RemoteSale,
    RemoteSaleItem,
    SyncCredential,
    SyncEvent,
)


def user_business(user):
    membership = (
        BusinessMembership.objects.select_related("business")
        .filter(user=user, is_active=True)
        .order_by("created_at")
        .first()
    )
    return membership.business if membership else None


def dashboard_metrics(business):
    today = timezone.localdate()
    sales_today = business.sales.filter(created_at_remote__date=today)
    purchases_today = business.purchases.filter(received_at_remote__date=today)
    return {
        "total_branches": business.branches.count(),
        "sales_count_today": sales_today.count(),
        "revenue_today": sales_today.aggregate(total=Sum("total"))["total"] or 0,
        "purchase_count_today": purchases_today.count(),
        "recent_sales": business.sales.select_related("branch").prefetch_related("items")[:8],
        "recent_syncs": business.sync_events.all()[:8],
    }


@transaction.atomic
def ingest_payload(*, credential, payload):
    business = credential.business
    business_info = payload.get("business", {})
    if business_info.get("name") and business.name != business_info["name"]:
        business.name = business_info["name"]
        business.save(update_fields=["name", "updated_at"])

    branch_map = {}
    branch_count = sale_count = purchase_count = inventory_count = 0

    for branch_data in payload.get("branches", []):
        branch, _ = RemoteBranch.objects.update_or_create(
            business=business,
            code=branch_data["code"],
            defaults={
                "external_id": branch_data.get("id"),
                "name": branch_data.get("name", branch_data["code"]),
                "address": branch_data.get("address", ""),
                "phone": branch_data.get("phone", ""),
                "is_active": branch_data.get("is_active", True),
            },
        )
        branch_map[branch.code] = branch
        branch_count += 1

    for sale_data in payload.get("sales", []):
        branch = branch_map.get(sale_data.get("branch"))
        sale, _ = RemoteSale.objects.update_or_create(
            business=business,
            branch=branch,
            external_id=sale_data["id"],
            defaults={
                "receipt_number": sale_data.get("receipt_number", ""),
                "cashier_name": sale_data.get("cashier", ""),
                "customer_name": sale_data.get("customer_name", ""),
                "customer_phone": sale_data.get("customer_phone", ""),
                "lane_name": sale_data.get("lane_name", ""),
                "payment_method": sale_data.get("payment_method", ""),
                "subtotal": sale_data.get("subtotal") or 0,
                "redeemed_points": sale_data.get("redeemed_points") or 0,
                "redeemed_amount": sale_data.get("redeemed_amount") or 0,
                "total": sale_data.get("total") or 0,
                "paid_amount": sale_data.get("paid_amount") or 0,
                "created_at_remote": parse_datetime(sale_data["created_at"]),
                "updated_at_remote": parse_datetime(sale_data["updated_at"]),
            },
        )
        sale.items.all().delete()
        RemoteSaleItem.objects.bulk_create(
            [
                RemoteSaleItem(
                    sale=sale,
                    line_index=index,
                    product_name=item.get("product", ""),
                    barcode=item.get("barcode", ""),
                    quantity=item.get("quantity") or 0,
                    unit_price=item.get("unit_price") or 0,
                    cost_price=item.get("cost_price") or 0,
                    line_total=item.get("line_total") or 0,
                    profit=item.get("profit") or 0,
                )
                for index, item in enumerate(sale_data.get("items", []), start=1)
            ]
        )
        sale_count += 1

    for purchase_data in payload.get("purchases", []):
        branch = branch_map.get(purchase_data.get("branch"))
        purchase, _ = RemotePurchase.objects.update_or_create(
            business=business,
            branch=branch,
            external_id=purchase_data["id"],
            defaults={
                "invoice_no": purchase_data.get("invoice_no", ""),
                "supplier_name": purchase_data.get("supplier", ""),
                "created_by_name": purchase_data.get("created_by", ""),
                "notes": purchase_data.get("notes", ""),
                "received_at_remote": parse_datetime(purchase_data["received_at"]),
            },
        )
        purchase.items.all().delete()
        RemotePurchaseItem.objects.bulk_create(
            [
                RemotePurchaseItem(
                    purchase=purchase,
                    line_index=index,
                    product_name=item.get("product", ""),
                    quantity=item.get("quantity") or 0,
                    cost_price=item.get("cost_price") or 0,
                    expiry_date=item.get("expiry_date") or None,
                )
                for index, item in enumerate(purchase_data.get("items", []), start=1)
            ]
        )
        purchase_count += 1

    for log_data in payload.get("inventory_logs", []):
        branch = branch_map.get(log_data.get("branch"))
        RemoteInventoryLog.objects.update_or_create(
            business=business,
            branch=branch,
            external_id=log_data["id"],
            defaults={
                "product_name": log_data.get("product", ""),
                "quantity": log_data.get("quantity") or 0,
                "action": log_data.get("action", ""),
                "source": log_data.get("source", ""),
                "reason": log_data.get("reason", ""),
                "reference": log_data.get("reference", ""),
                "before_quantity": log_data.get("before_quantity") or 0,
                "after_quantity": log_data.get("after_quantity") or 0,
                "created_by_name": log_data.get("created_by", ""),
                "created_at_remote": parse_datetime(log_data["created_at"]),
            },
        )
        inventory_count += 1

    credential.last_synced_at = timezone.now()
    credential.save(update_fields=["last_synced_at", "updated_at"])

    summary = {
        "branches": branch_count,
        "sales": sale_count,
        "purchases": purchase_count,
        "inventory_logs": inventory_count,
    }
    SyncEvent.objects.create(
        business=business,
        status=SyncEvent.Status.SUCCESS,
        message="Sync completed successfully.",
        payload_summary=summary,
    )
    return summary


def parse_request_json(request):
    return json.loads(request.body.decode("utf-8"))
