from django.db import migrations, models


def copy_group_validity(apps, schema_editor):
    AR = apps.get_model('core', 'AR')
    for ar in AR.objects.select_related('ar_group').all().iterator():
        group = ar.ar_group
        if group:
            ar.validity = group.validity_AR or 'Valid'
            ar.due_date = group.due_date
            ar.save(update_fields=['validity', 'due_date'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_mailing_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='ar',
            name='validity',
            field=models.CharField(blank=True, choices=[('Expired', 'Expired'), ('Valid', 'Valid')], default='Valid', max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='ar',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(copy_group_validity, migrations.RunPython.noop),
    ]
