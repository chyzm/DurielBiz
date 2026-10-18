import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0003_alter_branchstock_unique_together_and_more"),
        ("accounts", "0009_backfill_existing_business"),
    ]
    operations = [
        migrations.AlterField(model_name="branchstock", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
        migrations.AlterField(model_name="category", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
        migrations.AlterField(model_name="product", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
    ]
