import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_inventorylog_business"),
        ("accounts", "0009_backfill_existing_business"),
    ]
    operations = [
        migrations.AlterField(
            model_name="inventorylog",
            name="business",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business"),
        )
    ]
