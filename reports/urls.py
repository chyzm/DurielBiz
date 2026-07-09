from django.urls import path

from .views import (
    branch_delete,
    branch_list,
    branch_update,
    business_settings_view,
    dashboard,
    home,
    reports_category,
    reports_category_export_csv,
    reports_profit_by_product,
    reports_profit_export_csv,
    reports_profit_export_pdf,
    sync_auto,
    sync_export_view,
    sync_now,
)

app_name = "reports"

urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("branches/", branch_list, name="branch-list"),
    path("branches/<int:pk>/edit/", branch_update, name="branch-update"),
    path("branches/<int:pk>/delete/", branch_delete, name="branch-delete"),
    path("settings/business/", business_settings_view, name="business-settings"),
    path("settings/business/sync-now/", sync_now, name="sync-now"),
    path("settings/business/sync-auto/", sync_auto, name="sync-auto"),
    path("sync/export/", sync_export_view, name="sync-export"),
    path("reports/category/", reports_category, name="report-category"),
    path("reports/category/export/", reports_category_export_csv, name="report-category-export"),
    path("reports/profit/", reports_profit_by_product, name="report-profit"),
    path("reports/profit/export/", reports_profit_export_csv, name="report-profit-export"),
    path("reports/profit/export/pdf/", reports_profit_export_pdf, name="report-profit-export-pdf"),
]
