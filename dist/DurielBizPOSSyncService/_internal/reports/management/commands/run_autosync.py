import time

from django.core.management.base import BaseCommand

from reports.models import BusinessSettings
from reports.services import run_scheduled_cloud_sync


class Command(BaseCommand):
    help = "Runs automatic cloud sync on a loop or once."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run automatic sync check once and exit.")
        parser.add_argument(
            "--sleep-seconds",
            type=int,
            default=60,
            help="Polling interval in seconds when running continuously.",
        )

    def handle(self, *args, **options):
        run_once = options["once"]
        sleep_seconds = max(options["sleep_seconds"], 10)

        while True:
            settings_obj = BusinessSettings.get_solo()
            result = run_scheduled_cloud_sync(settings_obj=settings_obj)
            if result["ok"]:
                self.stdout.write(self.style.SUCCESS(result["message"]))
            elif run_once:
                self.stdout.write(result["message"])
            if run_once:
                return
            time.sleep(sleep_seconds)
