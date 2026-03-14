from django.contrib import admin
from django.urls import include, path

handler500 = "pos_system.error_views.server_error"


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("cloud/", include("cloudsync.urls")),
    path("products/", include("products.urls")),
    path("inventory/", include("inventory.urls")),
    path("purchases/", include("purchases.urls")),
    path("suppliers/", include("suppliers.urls")),
    path("notifications/", include("notifications.urls")),
    path("sales/", include("sales.urls")),
    path("", include("reports.urls")),
]
