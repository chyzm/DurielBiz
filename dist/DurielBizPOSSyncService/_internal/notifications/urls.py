from django.urls import path

from .views import expiring_products_api

app_name = "notifications"

urlpatterns = [
    path("expiring-products/", expiring_products_api, name="expiring-products"),
]
