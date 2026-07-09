import io

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    if "throttle_cache" in schema_editor.connection.introspection.table_names():
        return
    output = io.StringIO()
    call_command("createcachetable", "throttle_cache", verbosity=0, stdout=output, stderr=output)


def drop_cache_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS throttle_cache")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_branch"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
