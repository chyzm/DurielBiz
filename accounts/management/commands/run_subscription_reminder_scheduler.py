"""Run the daily subscription reminder job in a small dedicated container."""

import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import DatabaseError
from django.utils import timezone

from accounts.management.commands.send_subscription_reminders import Command as ReminderCommand
from accounts.models import Business

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run subscription reminders daily at 08:00 in the configured Django timezone."

    def add_arguments(self, parser):
        parser.add_argument("--hour", type=int, default=8, help="Local hour (0-23) to run reminders.")

    def handle(self, *args, **options):
        hour = options["hour"]
        if not 0 <= hour <= 23:
            raise ValueError("--hour must be between 0 and 23.")

        self.stdout.write(f"Subscription reminder scheduler active; daily run at {hour:02d}:00.")
        while True:
            try:
                Business.objects.exists()
                break
            except DatabaseError:
                logger.info("Waiting for the production database and migrations to become ready")
                time.sleep(5)
        try:
            # A restart after the scheduled hour still catches reminders. Sent
            # timestamps make this safe to repeat after a container restart.
            ReminderCommand().handle()
        except Exception:
            logger.exception("Startup subscription reminder run failed")
        while True:
            now = timezone.localtime()
            next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            time.sleep(max((next_run - now).total_seconds(), 1))
            try:
                ReminderCommand().handle()
            except Exception:
                # Keep the scheduler alive; Docker logs this stack trace and restarts
                # the process if the container itself exits unexpectedly.
                logger.exception("Daily subscription reminder job failed")
