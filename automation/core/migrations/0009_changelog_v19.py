from django.db import migrations
import django.utils.timezone


def seed_v19(apps, schema_editor):
    Changelog = apps.get_model('core', 'Changelog')
    Changelog.objects.get_or_create(
        version='v1.9.0',
        defaults={
            'title': 'Customer Additional Mailing Lists & Recipient Rules',
            'changes': [
                'Moved Additional Mailing Lists from individual Authorized Persons to the Customer profile.',
                'Added section 4 Additional Mailing Lists to Add/Edit Tenant.',
                'Specific Customer mode sends active Authorized Persons to TO and customer Additional Mailing Lists to CC.',
                'Site/Floor bulk sends active Authorized Persons plus Additional Mailing Lists of matching customers to BCC.',
                'Dynamic Mailing Group bulk sends active Authorized Persons plus Additional Mailing Lists of matching customers to BCC.',
                'Recipient deduplication keeps priority TO > CC > BCC.',
                'CSV import supports customer-level additional_mailing_list addresses separated by semicolons.',
            ],
            'released_at': django.utils.timezone.localdate(),
            'is_published': True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0008_customer_additional_mailing_list')]
    operations = [migrations.RunPython(seed_v19, migrations.RunPython.noop)]
