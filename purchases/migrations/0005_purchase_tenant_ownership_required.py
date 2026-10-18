import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("purchases", "0004_purchase_business_purchaseitem_business"),
        ("accounts", "0009_backfill_existing_business"),
    ]
    operations = [
        migrations.AlterField(model_name="purchase", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
        migrations.AlterField(model_name="purchaseitem", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
    ]
