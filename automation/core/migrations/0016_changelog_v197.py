from django.db import migrations
import django.utils.timezone


def seed_v197(apps, schema_editor):
    Changelog = apps.get_model('core', 'Changelog')
    Changelog.objects.get_or_create(
        version='v1.9.7',
        defaults={
            'title':'Reports, Checklist Compliance & Operational Refinement',
            'changes':[
                'Sequence Management added with monthly atomic numbering, copyable sequence numbers, responsive UI, Admin-only Audit/Void, and NTT-branded Excel reports.',
                'Customer Associations added for Contractor/WAF and Visitor/AVE with automatic Active, Expiring Soon, and Expired validity status.',
                'Mailing Group now supports explicit Specific Customers in addition to Site and multiple Floors.',
                'Notification templates retain the existing NTT DATA design while improving table alignment, multiline rendering, date/time handling, and generated EML filenames.',
                'Checklist JKT2/JKT3 modules added with compliance monitoring, backdate restrictions, PATROL BOND schedules/evidence, and Mizuho A3/B1 daily requirements.',
                'Checklist reports export to NTT-branded Excel and are restricted to Admin users.',
                'Remote Hands reports can be recorded and exported to PDF/Word using the corporate report format.',
                'Dashboard adds Customer Validity Status and Tenant Distribution by Site analytics.',
                'Static asset cache-busting updated to v1.9.7.',
            ],
            'released_at': django.utils.timezone.localdate(),
            'is_published': True,
        },
    )


class Migration(migrations.Migration):
    dependencies=[('core','0015_v197_remote_hands')]
    operations=[migrations.RunPython(seed_v197,migrations.RunPython.noop)]
