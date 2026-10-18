from django.apps import AppConfig


class SyncingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "syncing"

    def ready(self):
        from . import signals  # noqa: F401
