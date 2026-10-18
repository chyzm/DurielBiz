from django.db import migrations


def assign_legacy_business(apps, schema_editor):
    Business = apps.get_model("accounts", "Business")
    db = schema_editor.connection.alias
    business, _ = Business.objects.using(db).get_or_create(
        slug="existing-business",
        defaults={"name": "Existing Business", "is_active": True},
    )
    models_to_assign = [
        ("accounts", "ActivityLog"),
        ("accounts", "User"),
        ("reports", "Branch"),
        ("reports", "BusinessSettings"),
        ("products", "Category"),
        ("products", "Product"),
        ("products", "BranchStock"),
        ("suppliers", "Supplier"),
        ("sales", "Customer"),
        ("sales", "Sale"),
        ("sales", "SaleItem"),
        ("purchases", "Purchase"),
        ("purchases", "PurchaseItem"),
        ("inventory", "InventoryLog"),
    ]
    for app_label, model_name in models_to_assign:
        Model = apps.get_model(app_label, model_name)
        Model.objects.using(db).filter(business__isnull=True).update(business_id=business.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_business_activitylog_business_user_business"),
        ("inventory", "0005_inventorylog_business"),
        ("products", "0003_alter_branchstock_unique_together_and_more"),
        ("purchases", "0004_purchase_business_purchaseitem_business"),
        ("reports", "0007_branch_business_businesssettings_business_and_more"),
        ("sales", "0007_customer_business_sale_business_saleitem_business_and_more"),
        ("suppliers", "0002_supplier_business_alter_supplier_name_and_more"),
    ]

    operations = [migrations.RunPython(assign_legacy_business, migrations.RunPython.noop)]
