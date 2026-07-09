from django.urls import path

from .views import (
    branch_list,
    dashboard,
    ingest_api,
    inventory_export_csv,
    inventory_list,
    purchase_export_csv,
    purchase_list,
    rotate_token,
    sales_export_csv,
    sales_list,
    settings_view,
)

app_name = "cloudsync"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("branches/", branch_list, name="branches"),
    path("sales/", sales_list, name="sales"),
    path("sales/export.csv", sales_export_csv, name="sales-export-csv"),
    path("purchases/", purchase_list, name="purchases"),
    path("purchases/export.csv", purchase_export_csv, name="purchase-export-csv"),
    path("inventory/", inventory_list, name="inventory"),
    path("inventory/export.csv", inventory_export_csv, name="inventory-export-csv"),
    path("settings/", settings_view, name="settings"),
    path("settings/rotate-token/", rotate_token, name="rotate-token"),
    path("api/ingest/", ingest_api, name="ingest-api"),
]
