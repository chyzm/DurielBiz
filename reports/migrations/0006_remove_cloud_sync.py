from django.db import migrations

class Migration(migrations.Migration):
    """Remove obsolete sync settings while preserving legacy mirror tables.

    These records may be the only remaining copy of locally synchronized history.
    Keep them as an archive; a later data migration can reconcile them into the
    bidirectional sync system once the business/device pairing is established.
    """

    dependencies = [
        ("reports", "0005_business_settings_vat"),
    ]

    operations = [
        migrations.RemoveField(model_name="businesssettings", name="cloud_sync_enabled"),
        migrations.RemoveField(model_name="businesssettings", name="cloud_sync_token"),
        migrations.RemoveField(model_name="businesssettings", name="sync_dashboard_url"),
        migrations.RemoveField(model_name="businesssettings", name="auto_sync_enabled"),
        migrations.RemoveField(model_name="businesssettings", name="auto_sync_interval_minutes"),
        migrations.RemoveField(model_name="businesssettings", name="last_cloud_sync_at"),
    ]
