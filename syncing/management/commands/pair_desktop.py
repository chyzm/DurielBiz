import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from accounts.models import Business


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class Command(BaseCommand):
    help = "Pair this desktop with the cloud business using its referral key."

    def handle(self, *args, **options):
        data_dir = Path(os.getenv("DURIELBIZ_DATA_DIR", str(settings.DATA_DIR)))
        referral_path = data_dir / "referral-key.txt"
        if not referral_path.exists():
            raise CommandError("No business pairing key was provided by the installer.")
        referral_key = referral_path.read_text(encoding="utf-8").strip()
        sync_url = settings.DURIELBIZ_SYNC_URL
        if not referral_key:
            raise CommandError("The business pairing key is empty.")
        if not sync_url:
            raise CommandError("Configure DURIELBIZ_SYNC_URL in the desktop build before pairing.")
        parsed = urlparse(sync_url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise CommandError("Cloud pairing requires HTTPS except for localhost development.")

        pair_url = sync_url.rstrip("/") + "/pair/"
        request = urllib.request.Request(
            pair_url,
            data=json.dumps({"referral_key": referral_key, "device_name": os.getenv("COMPUTERNAME", "Desktop POS")}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            opener = urllib.request.build_opener(NoRedirectHandler)
            with opener.open(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            raise CommandError(f"Cloud pairing failed ({exc.code}): {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise CommandError("The cloud could not be reached. Check the internet connection and try again.") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CommandError("The cloud returned an invalid pairing response.") from exc

        try:
            device_id = str(result["device_id"])
            sync_token = str(result["sync_token"])
            cloud_business = result["business"]
            slug = str(cloud_business["slug"])
            if not device_id or not sync_token or not slug:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError("The cloud returned incomplete pairing details.") from exc

        expires_at = parse_datetime(cloud_business.get("subscription_expires_at") or "")
        business, created = Business._base_manager.get_or_create(
            slug=slug,
            defaults={
                "name": cloud_business["name"],
                "is_active": cloud_business.get("is_active", True),
                "subscription_plan": cloud_business.get("subscription_plan", Business.SubscriptionPlan.YEARLY),
                "subscription_expires_at": expires_at,
            },
        )
        if not created:
            business.name = cloud_business["name"]
            business.is_active = cloud_business.get("is_active", True)
            business.subscription_plan = cloud_business.get("subscription_plan", Business.SubscriptionPlan.YEARLY)
            business.subscription_expires_at = expires_at
            business.save(update_fields=["name", "is_active", "subscription_plan", "subscription_expires_at"])

        data_dir.mkdir(parents=True, exist_ok=True)
        credential_path = data_dir / "sync_credentials.json"
        temporary_path = credential_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps({
            "device_id": device_id,
            "token": sync_token,
            "business_slug": slug,
        }), encoding="utf-8")
        os.replace(temporary_path, credential_path)
        referral_path.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Desktop paired with cloud business {business.name}."))
