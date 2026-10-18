from django.urls import path

from .views import sync_api

urlpatterns = [path("", sync_api, name="sync-api")]
