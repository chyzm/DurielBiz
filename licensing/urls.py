from django.urls import path

from .views import activate_view

app_name = "licensing"

urlpatterns = [
    path("activate/", activate_view, name="activate"),
]
