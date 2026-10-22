from django.db import migrations, models
import django.db.models.deletion


def seed_existing_groups(apps, schema_editor):
    SiteLocation = apps.get_model("core", "SiteLocation")
    FloorLevel = apps.get_model("core", "FloorLevel")
    MailingGroup = apps.get_model("core", "MailingGroup")
    Changelog = apps.get_model("core", "Changelog")
    Changelog.objects.get_or_create(version="v1.7.0", defaults={"title":"Dynamic Mailing Group Management","changes":["Added database-driven Mailing Group CRUD.","Mailing Groups now use Site + selected Floors instead of hardcoded rules.","New customers are matched automatically by location; no manual group assignment is required.","Mailing Group bulk recipients remain BCC and are location-aware."],"is_published":True})
    site = SiteLocation.objects.filter(name__iexact="JKT2").first()
    if not site:
        return
    presets = [
        ("JKT2 General", [f"Level {n}" for n in range(1, 9)], "JKT2 Level 1-8"),
        ("JKT2 MP36", ["Level 6", "Level 7", "Level 8"], "JKT2 Level 6-8"),
        ("PM Level 7", ["Level 7"], "JKT2 Level 7 only"),
    ]
    for name, floor_names, desc in presets:
        floors = list(FloorLevel.objects.filter(site_location=site, name__in=floor_names))
        if not floors:
            continue
        group, _ = MailingGroup.objects.get_or_create(name=name, defaults={"site": site, "description": desc, "is_active": True})
        group.floors.set(floors)


class Migration(migrations.Migration):
    dependencies = [("core", "0004_activity_log_changelog")]
    operations = [
        migrations.CreateModel(
            name="MailingGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mailing_groups", to="core.sitelocation")),
                ("floors", models.ManyToManyField(blank=True, related_name="mailing_groups", to="core.floorlevel")),
            ],
            options={"db_table": "mailing_groups", "ordering": ["site__name", "name"]},
        ),
        migrations.RunPython(seed_existing_groups, migrations.RunPython.noop),
    ]
