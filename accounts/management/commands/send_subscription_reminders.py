from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from accounts.models import Business, User


class Command(BaseCommand):
    help = "Email tenant administrators when their business subscription is close to expiry."

    def handle(self, *args, **options):
        now = timezone.now()
        businesses = Business.objects.filter(is_active=True, subscription_expires_at__gt=now)
        sent_count = 0
        for business in businesses.iterator():
            remaining = business.subscription_expires_at - now
            if remaining <= timedelta(days=1) and not business.reminder_1_day_sent_at:
                reminder_field = "reminder_1_day_sent_at"
                label = "within 1 day"
            elif remaining <= timedelta(days=7) and not business.reminder_7_days_sent_at:
                reminder_field = "reminder_7_days_sent_at"
                label = "within 7 days"
            else:
                continue

            recipients = list(
                User.objects.filter(
                    business=business,
                    role=User.Role.ADMIN,
                    is_active=True,
                ).exclude(email="").values_list("email", flat=True).distinct()
            )
            if not recipients:
                continue
            expires = timezone.localtime(business.subscription_expires_at).strftime("%d %B %Y, %I:%M %p")
            sent = send_mail(
                subject=f"DurielBiz subscription expires {label}",
                message=(
                    f"Hello {business.name} administrator,\n\n"
                    f"Your DurielBiz subscription expires on {expires}. "
                    "Please contact DurielTech to renew it and avoid interruption to sign-in.\n\n"
                    "DurielTech Support\n07031016787\ninfo@durieltech.com.ng"
                ),
                from_email=None,
                recipient_list=recipients,
                fail_silently=False,
            )
            if sent:
                Business.objects.filter(pk=business.pk).update(**{reminder_field: now})
                sent_count += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} subscription reminder(s)."))
