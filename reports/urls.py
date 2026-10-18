from django.urls import path

from .views import (
    branch_delete,
    branch_list,
    branch_update,
    business_settings_view,
    dashboard,
    reports_category,
    reports_category_export_csv,
    reports_profit_by_product,
    reports_profit_export_csv,
    reports_profit_export_pdf,
)

app_name = "reports"

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("branches/", branch_list, name="branch-list"),
    path("branches/<signed_int:pk>/edit/", branch_update, name="branch-update"),
    path("branches/<signed_int:pk>/delete/", branch_delete, name="branch-delete"),
    path("settings/business/", business_settings_view, name="business-settings"),
    path("reports/category/", reports_category, name="report-category"),
    path("reports/category/export/", reports_category_export_csv, name="report-category-export"),
    path("reports/profit/", reports_profit_by_product, name="report-profit"),
    path("reports/profit/export/", reports_profit_export_csv, name="report-profit-export"),
    path("reports/profit/export/pdf/", reports_profit_export_pdf, name="report-profit-export-pdf"),
]
