from django.urls import path

from .views import branch_list, dashboard, ingest_api, rotate_token, sales_list, settings_view, signup

app_name = "cloudsync"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("signup/", signup, name="signup"),
    path("branches/", branch_list, name="branches"),
    path("sales/", sales_list, name="sales"),
    path("settings/", settings_view, name="settings"),
    path("settings/rotate-token/", rotate_token, name="rotate-token"),
    path("api/ingest/", ingest_api, name="ingest-api"),
]
