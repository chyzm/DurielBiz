import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0007_customer_business_sale_business_saleitem_business_and_more"),
        ("accounts", "0009_backfill_existing_business"),
    ]
    operations = [
        migrations.AlterField(model_name="customer", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
        migrations.AlterField(model_name="sale", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
        migrations.AlterField(model_name="saleitem", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
    ]
