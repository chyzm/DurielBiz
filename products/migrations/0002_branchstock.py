from django.db import migrations, models
import django.db.models.deletion


def seed_branch_stock(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    BranchStock = apps.get_model("products", "BranchStock")
    Branch = apps.get_model("reports", "Branch")
    BusinessSettings = apps.get_model("reports", "BusinessSettings")

    settings_obj = BusinessSettings.objects.filter(pk=1).first()
    branch = None
    if settings_obj and settings_obj.default_branch_id:
        branch = Branch.objects.filter(pk=settings_obj.default_branch_id).first()
    if branch is None:
        branch = Branch.objects.filter(is_active=True).order_by("name").first() or Branch.objects.order_by("name").first()
    if branch is None:
        return

    for product in Product.objects.exclude(quantity=0):
        BranchStock.objects.get_or_create(
            branch=branch,
            product=product,
            defaults={"quantity": product.quantity},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_branch_businesssettings_cloud_sync_enabled_and_more"),
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BranchStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "branch",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_stocks", to="reports.branch"),
                ),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_stocks", to="products.product"),
                ),
            ],
            options={
                "ordering": ["branch__name", "product__name"],
                "unique_together": {("branch", "product")},
            },
        ),
        migrations.RunPython(seed_branch_stock, migrations.RunPython.noop),
    ]
