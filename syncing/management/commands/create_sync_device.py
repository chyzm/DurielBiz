import secrets
import uuid

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Business
from syncing.models import SyncDevice


class Command(BaseCommand):
    help = "Create a cloud-to-desktop sync credential for one business."

    def add_arguments(self, parser):
        parser.add_argument("business_slug")
        parser.add_argument("name")

    def handle(self, *args, **options):
        business = Business.objects.filter(slug=options["business_slug"], is_active=True).first()
        if business is None:
            raise CommandError("An active business with that slug was not found.")
        device_id = uuid.uuid4()
        secret = secrets.token_urlsafe(40)
        SyncDevice.objects.create(
            id=device_id,
            business=business,
            name=options["name"],
            token_hash=make_password(secret),
        )
        self.stdout.write(self.style.SUCCESS("Sync device created. Save this credential securely; the secret is shown only once."))
        self.stdout.write(f"DURIELBIZ_SYNC_DEVICE_ID={device_id}")
        self.stdout.write(f"DURIELBIZ_SYNC_TOKEN={device_id}:{secret}")
        self.stdout.write(f"DURIELBIZ_SYNC_BUSINESS_SLUG={business.slug}")
