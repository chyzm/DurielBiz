import json

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder

from accounts.tenancy import TenantOwnedModel


def syncable_models():
    result = []
    for model in apps.get_models():
        if model._meta.app_label == "syncing":
            continue
        if model._meta.label_lower == "accounts.user" or issubclass(model, TenantOwnedModel):
            result.append(model)
    return result


def serialize_object(instance):
    values = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name == "business":
            continue
        values[field.attname] = getattr(instance, field.attname)
    return json.loads(json.dumps({"business_slug": instance.business.slug, "values": values}, cls=DjangoJSONEncoder))


def ordered_syncable_models():
    models = syncable_models()
    model_set = set(models)
    ordered = []
    remaining = set(models)
    while remaining:
        ready = sorted(
            [model for model in remaining if not any(
                field.is_relation and field.remote_field and field.remote_field.model in remaining
                for field in model._meta.concrete_fields
            )],
            key=lambda model: (model._meta.app_label, model._meta.model_name),
        )
        if not ready:
            ready = [sorted(remaining, key=lambda model: model._meta.label_lower)[0]]
        for model in ready:
            ordered.append(model)
            remaining.remove(model)
    return ordered


def model_for_label(label):
    try:
        model = apps.get_model(label)
    except (LookupError, ValueError):
        return None
    if model and (model._meta.label_lower == "accounts.user" or issubclass(model, TenantOwnedModel)):
        return model
    return None
