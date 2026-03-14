from django.urls import path

from .views import supplier_create, supplier_delete, supplier_detail, supplier_list, supplier_update

app_name = "suppliers"

urlpatterns = [
    path("", supplier_list, name="list"),
    path("new/", supplier_create, name="create"),
    path("<int:pk>/", supplier_detail, name="detail"),
    path("<int:pk>/edit/", supplier_update, name="update"),
    path("<int:pk>/delete/", supplier_delete, name="delete"),
]
