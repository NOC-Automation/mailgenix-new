from django.db import migrations
import django.utils.timezone


def seed_v193(apps, schema_editor):
    Changelog = apps.get_model("core", "Changelog")
    Changelog.objects.get_or_create(
        version="v1.9.3",
        defaults={
            "title": "Support Group CSV Import & User CRUD",
            "changes": [
                "Added Support Group CSV import and downloadable CSV template inside Customer Workspace.",
                "Normal authenticated User role can add, edit, and delete Support Group records.",
                "Support Group CSV can optionally scope personnel to an existing customer Site/Floor/Rack.",
                "Support Group import actions are recorded in Activity Log.",
            ],
            "released_at": django.utils.timezone.localdate(),
            "is_published": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0009_changelog_v19")]
    operations = [migrations.RunPython(seed_v193, migrations.RunPython.noop)]
