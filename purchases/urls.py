from django.urls import path

from .views import purchase_create, purchase_delete, purchase_detail, purchase_list, purchase_update

app_name = "purchases"

urlpatterns = [
    path("", purchase_list, name="list"),
    path("receive/", purchase_create, name="create"),
    path("<signed_int:pk>/", purchase_detail, name="detail"),
    path("<signed_int:pk>/edit/", purchase_update, name="update"),
    path("<signed_int:pk>/delete/", purchase_delete, name="delete"),
]
