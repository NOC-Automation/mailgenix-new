from django.db import migrations
import django.utils.timezone


def seed_v18(apps, schema_editor):
    Changelog = apps.get_model('core', 'Changelog')
    Changelog.objects.get_or_create(
        version='v1.8.0',
        defaults={
            'title': 'Unified Customer Profile & Responsive UI',
            'changes': [
                'Rebuilt Add/Edit Tenant as one customer profile with multiple Location/Rack rows.',
                'Authorized Persons are customer-wide and no longer assigned to individual racks.',
                'Validity status is calculated automatically as Active, Expiring Soon, or Expired from Validity Date.',
                'Removed legacy Table View and moved the working CSV import directly into Customer Workspace.',
                'CSV import now deduplicates repeated customer/AR data and supports location-only rows.',
                'Notification template cards now use Preview only; the decorative template icon box and per-card Go button were removed.',
                'Recipient rules now match impacted customers by rack location and notify all non-expired ARs for those customers.',
            ],
            'released_at': django.utils.timezone.localdate(),
            'is_published': True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0006_ar_profile_validity')]
    operations = [migrations.RunPython(seed_v18, migrations.RunPython.noop)]
