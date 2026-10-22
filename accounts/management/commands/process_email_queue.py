from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from accounts.models import EmailOutbox
from accounts.otp import OTP_VALIDITY_MINUTES


class Command(BaseCommand):
    help = "Send pending welcome and password recovery emails from the durable email queue."

    def handle(self, *args, **options):
        sent_count = 0
        failed_count = 0

        while True:
            with transaction.atomic():
                job = (
                    EmailOutbox.objects.select_for_update()
                    .filter(status=EmailOutbox.Status.PENDING, next_attempt_at__lte=timezone.now())
                    .order_by(
                        Case(
                            When(kind=EmailOutbox.Kind.PASSWORD_RESET, then=Value(0)),
                            default=Value(1),
                            output_field=IntegerField(),
                        ),
                        "created_at",
                    )
                    .first()
                )
                if job is None:
                    break

                job.attempts += 1
                try:
                    sent = send_mail(
                        subject=job.subject,
                        message=job.message,
                        from_email=None,
                        recipient_list=[job.recipient],
                        fail_silently=False,
                    )
                    if not sent:
                        raise RuntimeError("Email backend did not send the message.")
                except Exception as exc:
                    job.last_error = str(exc)[:4000]
                    job.next_attempt_at = timezone.now() + timedelta(
                        minutes=min(2 ** min(job.attempts, 6), 60)
                    )
                    job.save(update_fields=["attempts", "last_error", "next_attempt_at"])
                    failed_count += 1
                    self.stderr.write(f"Email job {job.pk} failed; it will be retried: {exc}")
                    continue

                now = timezone.now()
                job.status = EmailOutbox.Status.SENT
                job.sent_at = now
                job.last_error = ""
                job.save(update_fields=["attempts", "status", "sent_at", "last_error"])
                otp = job.otp
                if otp is not None:
                    otp.expires_at = now + timedelta(minutes=OTP_VALIDITY_MINUTES)
                    otp.save(update_fields=["expires_at"])
                sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Sent {sent_count} email(s); {failed_count} failed and were scheduled for retry.")
        )
