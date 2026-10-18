from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def start_existing_subscriptions(apps, schema_editor):
    Business = apps.get_model("accounts", "Business")
    now = timezone.now()
    Business.objects.using(schema_editor.connection.alias).filter(subscription_expires_at__isnull=True).update(
        subscription_plan="yearly",
        subscription_expires_at=now + timedelta(days=365),
    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_activitylog_business_required")]

    operations = [
        migrations.AddField(
            model_name="business",
            name="subscription_plan",
            field=models.CharField(
                choices=[("monthly", "1 month"), ("yearly", "1 year")],
                default="yearly",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="subscription_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="business",
            name="reminder_7_days_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="business",
            name="reminder_1_day_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(start_existing_subscriptions, migrations.RunPython.noop),
    ]
