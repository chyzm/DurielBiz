from django.urls import path

from .views import branch_delete, branch_list, branch_update, business_settings_view, dashboard, sync_export_view

app_name = "reports"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("branches/", branch_list, name="branch-list"),
    path("branches/<int:pk>/edit/", branch_update, name="branch-update"),
    path("branches/<int:pk>/delete/", branch_delete, name="branch-delete"),
    path("settings/business/", business_settings_view, name="business-settings"),
    path("sync/export/", sync_export_view, name="sync-export"),
]
