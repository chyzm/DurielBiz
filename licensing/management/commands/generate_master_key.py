import hashlib
import secrets

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate a new master activation key. Run this ONCE, on your own machine — keep the plaintext key secret and never ship it."

    def handle(self, *args, **options):
        master_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(master_key.encode("utf-8")).hexdigest()

        self.stdout.write(self.style.WARNING("Activation key — save this somewhere offline and secret. This is what you type into a client's activation screen to unlock it:"))
        self.stdout.write(master_key)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Paste this HASH into LICENSE_MASTER_KEY_HASH in .env before building the distributable (safe to ship — it cannot be reversed back into the key):"))
        self.stdout.write(key_hash)
