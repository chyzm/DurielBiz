from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path, register_converter

from .converters import SignedIntConverter

register_converter(SignedIntConverter, "signed_int")

from accounts.views import AccountLoginView

handler500 = "pos_system.error_views.server_error"


urlpatterns = [
    path("api/sync/", include("syncing.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("products/", include("products.urls")),
    path("inventory/", include("inventory.urls")),
    path("purchases/", include("purchases.urls")),
    path("suppliers/", include("suppliers.urls")),
    path("notifications/", include("notifications.urls")),
    path("sales/", include("sales.urls")),
    path("licensing/", include("licensing.urls")),
    re_path(r"^$", AccountLoginView.as_view(), name="root"),
    path("", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
