import json
import uuid

from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Business
from accounts.tenancy import reset_current_business_id, set_current_business_id

from .apply import SyncConflict, apply_change
from .models import SyncChange, SyncDevice
from .protocol import ordered_syncable_models, serialize_object

MAX_BATCH = 1000
MAX_BODY_BYTES = 5 * 1024 * 1024
SNAPSHOT_PAGE_SIZE = 250


def _device_from_request(request):
    authorization = request.headers.get("Authorization", "")
    scheme, _, credential = authorization.partition(" ")
    device_text, separator, secret = credential.partition(":")
    if scheme.lower() != "bearer" or not separator or not secret:
        return None
    try:
        device_id = uuid.UUID(device_text)
    except (TypeError, ValueError, AttributeError):
        return None
    device = SyncDevice.objects.select_related("business").filter(pk=device_id, is_active=True).first()
    return device if device and check_password(secret, device.token_hash) else None


@csrf_exempt
@require_POST
def sync_api(request):
    try:
        body_size = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid request size."}, status=400)
    if body_size > MAX_BODY_BYTES:
        return JsonResponse({"error": "Request batch is too large."}, status=413)
    device = _device_from_request(request)
    if device is None:
        return JsonResponse({"error": "Invalid or inactive sync device."}, status=401)
    try:
        request_data = json.loads(request.body or b"{}")
        if not isinstance(request_data, dict):
            raise ValueError
        if str(request_data.get("device_id", "")) != str(device.pk):
            raise ValueError
        changes = request_data.get("changes", [])
        after = int(request_data.get("after", 0))
        bootstrap = bool(request_data.get("bootstrap", False))
        snapshot_model_index = int(request_data.get("snapshot_model_index", 0))
        snapshot_after_pk = int(request_data.get("snapshot_after_pk", 0))
        snapshot_cursor = request_data.get("snapshot_cursor")
        if snapshot_cursor is not None:
            snapshot_cursor = int(snapshot_cursor)
        if not isinstance(changes, list) or len(changes) > MAX_BATCH or after < 0:
            raise ValueError
        if snapshot_model_index < 0 or snapshot_after_pk < 0 or (snapshot_cursor is not None and snapshot_cursor < 0):
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"error": "Invalid sync request."}, status=400)

    tenant_token = set_current_business_id(device.business_id)
    try:
        with transaction.atomic():
            for event in changes:
                if not isinstance(event, dict) or not all(
                    key in event for key in ("event_id", "model", "pk", "operation", "payload")
                ):
                    raise SyncConflict("A sync event was malformed.")
                if not isinstance(event["payload"], dict) or event["operation"] not in SyncChange.Operation.values:
                    raise SyncConflict("A sync event was malformed.")
                try:
                    event["event_id"] = str(uuid.UUID(str(event["event_id"])))
                    event["pk"] = int(event["pk"])
                except (TypeError, ValueError, AttributeError) as exc:
                    raise SyncConflict("A sync event identifier was invalid.") from exc
                existing = SyncChange.objects.filter(event_id=event["event_id"]).exists()
                if not existing:
                    apply_change(event, device.business, record_cloud_event=True)
            device.last_seen_at = timezone.now()
            device.save(update_fields=["last_seen_at"])

            if bootstrap:
                cursor = snapshot_cursor
                if cursor is None:
                    cursor = SyncChange.objects.filter(business=device.business).order_by("-pk").values_list("pk", flat=True).first() or 0
                snapshot = []
                models = ordered_syncable_models()
                model_index = snapshot_model_index
                after_pk = snapshot_after_pk
                while model_index < len(models) and len(snapshot) < SNAPSHOT_PAGE_SIZE:
                    model = models[model_index]
                    page = list(
                        model._base_manager.filter(
                            business_id=device.business_id, pk__gt=after_pk
                        ).order_by("pk")[: SNAPSHOT_PAGE_SIZE - len(snapshot)]
                    )
                    snapshot.extend({
                        "model": model._meta.label_lower,
                        "pk": instance.pk,
                        "operation": SyncChange.Operation.UPSERT,
                        "event_id": str(uuid.uuid4()),
                        "payload": serialize_object(instance),
                    } for instance in page)
                    if len(snapshot) == SNAPSHOT_PAGE_SIZE:
                        after_pk = page[-1].pk
                        break
                    model_index += 1
                    after_pk = 0
                has_more = model_index < len(models)
                return JsonResponse({
                    "snapshot": snapshot, "changes": [], "cursor": cursor,
                    "next_model_index": model_index if has_more else None,
                    "next_pk": after_pk if has_more else None,
                })

            outgoing = list(
                SyncChange.objects.filter(business=device.business, pk__gt=after)
                .order_by("pk")[:MAX_BATCH]
            )
            serialized = [{
                "sequence": change.pk,
                "event_id": str(change.event_id),
                "model": change.model_label,
                "pk": change.object_pk,
                "operation": change.operation,
                "payload": change.payload,
                "occurred_at": change.occurred_at.isoformat(),
            } for change in outgoing]
            cursor = outgoing[-1].pk if outgoing else after
            return JsonResponse({"snapshot": None, "changes": serialized, "cursor": cursor})
    except SyncConflict as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    finally:
        reset_current_business_id(tenant_token)
