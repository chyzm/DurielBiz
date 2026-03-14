from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0003_branch_businesssettings_cloud_sync_enabled_and_more"),
        ("accounts", "0002_activitylog"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="branch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="users",
                to="reports.branch",
            ),
        ),
    ]
