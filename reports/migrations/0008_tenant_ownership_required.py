import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0007_branch_business_businesssettings_business_and_more"),
        ("accounts", "0009_backfill_existing_business"),
    ]
    operations = [
        migrations.AlterField(model_name="branch", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
        migrations.AlterField(model_name="businesssettings", name="business", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.business")),
    ]
