import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Business
from accounts.tenancy import reset_current_business_id, set_current_business_id
from syncing.apply import SyncConflict, apply_change
from syncing.models import SyncChange, SyncCheckpoint
from syncing.protocol import ordered_syncable_models


class Command(BaseCommand):
    help = "Synchronize this desktop database with its paired DurielBiz cloud business."

    def add_arguments(self, parser):
        parser.add_argument("--bootstrap-from-cloud", action="store_true", help="Replace this business's local data with the cloud snapshot on first pairing.")
        parser.add_argument("--loop", action="store_true", help="Keep syncing in the background until the process exits.")
        parser.add_argument("--interval", type=int, default=60, help="Seconds between background sync attempts.")

    def handle(self, *args, **options):
        url = os.getenv("DURIELBIZ_SYNC_URL", "").strip()
        token = os.getenv("DURIELBIZ_SYNC_TOKEN", "").strip()
        device_id = os.getenv("DURIELBIZ_SYNC_DEVICE_ID", "").strip()
        slug = os.getenv("DURIELBIZ_SYNC_BUSINESS_SLUG", "").strip()
        if not url or not token or not device_id or not slug:
            raise CommandError("Set DURIELBIZ_SYNC_URL, DURIELBIZ_SYNC_TOKEN, DURIELBIZ_SYNC_DEVICE_ID, and DURIELBIZ_SYNC_BUSINESS_SLUG first.")
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" and parsed_url.hostname not in {"localhost", "127.0.0.1"}:
            raise CommandError("Cloud sync requires HTTPS except for localhost development.")
        if options["loop"]:
            interval = max(15, options["interval"])
            lock_path = Path(os.getenv("DURIELBIZ_DATA_DIR", ".")) / "sync_service.pid"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    old_pid = int(lock_path.read_text(encoding="utf-8").strip())
                    os.kill(old_pid, 0)
                except (OSError, ValueError):
                    lock_path.unlink(missing_ok=True)
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                else:
                    raise CommandError("A desktop sync service is already running.")
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            try:
                while True:
                    try:
                        self.sync_once(url, token, device_id, slug, options["bootstrap_from_cloud"])
                        options["bootstrap_from_cloud"] = False
                    except Exception as exc:  # Keep the desktop usable through outages; retry next interval.
                        self.stderr.write(f"Cloud sync delayed: {exc}")
                    time.sleep(interval)
            finally:
                lock_path.unlink(missing_ok=True)
        else:
            self.sync_once(url, token, device_id, slug, options["bootstrap_from_cloud"])

    def sync_once(self, url, token, device_id, slug, bootstrap):
        business = Business._base_manager.filter(slug=slug).first()
        if business is None:
            raise CommandError("The paired business does not exist in this desktop database.")
        checkpoint, _ = SyncCheckpoint.objects.get_or_create(device_id=device_id)
        bootstrap = bootstrap or not checkpoint.is_bootstrapped
        changes = []
        if not bootstrap:
            local_events = SyncChange.objects.filter(business=business, pk__gt=checkpoint.pushed_cursor).order_by("pk")[:1000]
            for change in local_events:
                changes.append({
                    "event_id": str(change.event_id), "model": change.model_label,
                    "pk": change.object_pk, "operation": change.operation,
                    "payload": change.payload, "occurred_at": change.occurred_at.isoformat(),
                })
        request_values = {
            "device_id": device_id,
            "changes": changes,
            "after": 0 if bootstrap else checkpoint.pulled_cursor,
            "bootstrap": bootstrap,
        }

        def send(payload):
            request = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"), method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read(1000).decode("utf-8", errors="replace")
                raise CommandError(f"Cloud sync rejected the batch ({exc.code}): {body}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise CommandError("Cloud is unavailable; local checkout remains available and sync will retry.") from exc

        result = send(request_values)
        if bootstrap:
            snapshot = list(result.get("snapshot") or [])
            while result.get("next_model_index") is not None:
                request_values.update({
                    "snapshot_model_index": result["next_model_index"],
                    "snapshot_after_pk": result["next_pk"],
                    "snapshot_cursor": result["cursor"],
                })
                result = send(request_values)
                snapshot.extend(result.get("snapshot") or [])
            result["snapshot"] = snapshot

        tenant_token = set_current_business_id(business.pk)
        try:
            with transaction.atomic():
                if bootstrap:
                    self.replace_local_business_data(business)
                    incoming = result.get("snapshot") or []
                else:
                    incoming = result.get("changes") or []
                for event in incoming:
                    normalized = {
                        "event_id": event["event_id"], "model": event["model"],
                        "pk": event["pk"], "operation": event["operation"],
                        "payload": event.get("payload") or {},
                    }
                    # Events just uploaded by this desktop are already represented
                    # locally; skip their cloud echo while still advancing cursor.
                    if not SyncChange.objects.filter(event_id=normalized["event_id"]).exists():
                        apply_change(normalized, business, replay_inventory=not bootstrap)
                checkpoint.pulled_cursor = int(result.get("cursor", checkpoint.pulled_cursor))
                if bootstrap:
                    checkpoint.pushed_cursor = 0
                    checkpoint.is_bootstrapped = True
                elif changes:
                    checkpoint.pushed_cursor = max(
                        event.pk for event in SyncChange.objects.filter(
                            business=business, event_id__in=[change["event_id"] for change in changes]
                        )
                    )
                checkpoint.save(update_fields=["pushed_cursor", "pulled_cursor", "is_bootstrapped", "updated_at"])
        except SyncConflict as exc:
            raise CommandError(str(exc)) from exc
        finally:
            reset_current_business_id(tenant_token)
        self.stdout.write(self.style.SUCCESS(f"Cloud sync complete: {len(changes)} local change(s) sent, {len(incoming)} cloud change(s) received."))

    def replace_local_business_data(self, business):
        for model in reversed(ordered_syncable_models()):
            model._base_manager.filter(business_id=business.pk).delete()
        SyncChange.objects.filter(business=business).delete()
