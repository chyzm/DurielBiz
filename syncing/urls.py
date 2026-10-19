from django.urls import path

from .views import pair_api, sync_api

urlpatterns = [
    path("", sync_api, name="sync-api"),
    path("pair/", pair_api, name="pair-api"),
]
