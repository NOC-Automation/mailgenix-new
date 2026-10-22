from django.db import migrations
import django.utils.timezone

def seed_v195(apps, schema_editor):
    Changelog = apps.get_model('core', 'Changelog')
    Changelog.objects.get_or_create(
        version='v1.9.5',
        defaults={
            'title':'Notification Workflow, HTML Templates & Live Data',
            'changes':[
                'Mailing List redesigned into template selection, dynamic notification details, recipient scope, resolved recipients, final preview, and Generate Draft steps.',
                'Notification templates now use Category / Type / Variant hierarchy with contextual Outage Update Type.',
                'Outage Occurrence/Status/Recovery/Root Cause dynamically controls form fields, subject, and HTML output; Fault Recovering Time remains a row and uses a dash until recovery.',
                'Outage Service Impact is standardized as read-only and Additional Information always keeps the standard closing message.',
                'Email templates use a consistent 600px Outlook-friendly table layout with dynamic placeholders and JKT2/JKT3 site mapping.',
                'Generated .eml includes Subject, TO, CC, BCC, HTML body, and CID-embedded NTT DATA logo.',
                'Static assets are versioned for v1.9.5 to avoid manual hard refresh after deployment.',
                'Background live-state polling detects updates from other users and refreshes the active Tenant/Support Group workspace without reloading an open edit form.',
            ],
            'released_at': django.utils.timezone.localdate(),
            'is_published': True,
        },
    )

class Migration(migrations.Migration):
    dependencies=[('core','0011_changelog_v194')]
    operations=[migrations.RunPython(seed_v195,migrations.RunPython.noop)]
