from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0012_alter_salesreconciliationline_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="checkout_idempotency_key",
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
