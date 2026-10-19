from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0008_tenant_ownership_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="businesssettings",
            name="sync_referral_key_hash",
            field=models.CharField(blank=True, default="", max_length=256),
        ),
        migrations.AddField(
            model_name="businesssettings",
            name="sync_referral_key_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
