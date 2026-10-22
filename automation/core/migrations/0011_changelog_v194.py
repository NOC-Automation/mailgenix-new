from django.db import migrations
import django.utils.timezone


def seed_v194(apps, schema_editor):
    Changelog = apps.get_model("core", "Changelog")
    Changelog.objects.get_or_create(
        version="v1.9.4",
        defaults={
            "title": "Recipient Scope, UI & Access Refinements",
            "changes": [
                "Support Group CSV template/import is now Admin-only while User can still add, edit, and delete Support Group records.",
                "Tenant List Site Group headers are collapsible accordions with state preserved in the browser.",
                "Dashboard spacing, Changelog presentation, and Support Group status visualization were refined.",
                "Mailing Group floor selection uses natural numeric ordering and an updated management UI.",
                "Mailing List now has explicit Site/Floor, Specific Customer, and Mailing Group recipient scopes with group scope statistics.",
                "Resolved TO/CC/BCC fields are read-only but remain selectable, copyable, and vertically resizable.",
                "User Management now presents only Admin/User roles and removes Staff/Superuser UI columns.",
                "Login sessions use a fixed 24-hour lifetime with secure cookie defaults for production.",
            ],
            "released_at": django.utils.timezone.localdate(),
            "is_published": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0010_changelog_v193_support_group_csv")]
    operations = [migrations.RunPython(seed_v194, migrations.RunPython.noop)]
