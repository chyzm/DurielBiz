from django.core.management.base import BaseCommand

from invoicing.services import due_for_expiry_notice, send_expiry_notice


class Command(BaseCommand):
    help = "Send invoicing subscription expiry reminder emails for subscriptions expiring in 3 days."

    def handle(self, *args, **options):
        sent_count = 0
        skipped_count = 0
        for subscription in due_for_expiry_notice():
            try:
                if send_expiry_notice(subscription):
                    sent_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f"Failed to send reminder for {subscription.business.name}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"Subscription reminder run complete. Sent: {sent_count}, skipped: {skipped_count}"))
