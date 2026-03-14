from django.urls import path

from .views import inventory_adjustment, inventory_delete, inventory_detail, inventory_export_csv, inventory_overview, inventory_update

app_name = "inventory"

urlpatterns = [
    path("", inventory_overview, name="overview"),
    path("export.csv", inventory_export_csv, name="export-csv"),
    path("adjust/", inventory_adjustment, name="adjust"),
    path("logs/<int:pk>/", inventory_detail, name="detail"),
    path("logs/<int:pk>/edit/", inventory_update, name="update"),
    path("logs/<int:pk>/delete/", inventory_delete, name="delete"),
]
