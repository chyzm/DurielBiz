import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class SyncDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("accounts.Business", on_delete=models.CASCADE, related_name="sync_devices")
    name = models.CharField(max_length=120)
    token_hash = models.CharField(max_length=256)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)


class SyncChange(models.Model):
    class Operation(models.TextChoices):
        UPSERT = "upsert", "Upsert"
        DELETE = "delete", "Delete"

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    business = models.ForeignKey("accounts.Business", on_delete=models.CASCADE, related_name="sync_changes")
    model_label = models.CharField(max_length=100)
    object_pk = models.BigIntegerField()
    operation = models.CharField(max_length=10, choices=Operation.choices)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["pk"]
        indexes = [models.Index(fields=["business", "id"])]


class SyncAppliedEvent(models.Model):
    event_id = models.UUIDField(unique=True)
    applied_at = models.DateTimeField(auto_now_add=True)


class SyncCheckpoint(models.Model):
    device_id = models.UUIDField(unique=True)
    pushed_cursor = models.BigIntegerField(default=0)
    pulled_cursor = models.BigIntegerField(default=0)
    is_bootstrapped = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
