from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Encrypt a value for use inside .env as ENC(...). Requires cryptography."

    def add_arguments(self, parser):
        parser.add_argument("--value", help="Plain text value to encrypt.")
        parser.add_argument(
            "--generate-key",
            action="store_true",
            help="Generate a Fernet key for DURIELBIZ_ENV_KEY.",
        )
        parser.add_argument(
            "--key",
            help="Encryption key. Defaults to DURIELBIZ_ENV_KEY from the environment.",
        )

    def handle(self, *args, **options):
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise CommandError("Install 'cryptography' first to use this command.") from exc

        if options["generate_key"]:
            self.stdout.write(Fernet.generate_key().decode("utf-8"))
            return

        raw_value = options.get("value")
        if not raw_value:
            raise CommandError("Provide --value or use --generate-key.")

        key = options.get("key")
        if not key:
            import os

            key = os.getenv("DURIELBIZ_ENV_KEY")
        if not key:
            raise CommandError("Provide --key or set DURIELBIZ_ENV_KEY.")

        encrypted = Fernet(key.encode("utf-8")).encrypt(raw_value.encode("utf-8")).decode("utf-8")
        self.stdout.write(f"ENC({encrypted})")
