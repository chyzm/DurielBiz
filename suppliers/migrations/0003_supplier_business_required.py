import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("suppliers", "0002_supplier_business_alter_supplier_name_and_more"),
        ("accounts", "0009_backfill_existing_business"),
    ]
    operations = [
        migrations.AlterField(
            model_name="supplier",
            name="business",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business"),
        )
    ]
