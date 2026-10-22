from django.db import migrations, models
import django.db.models.deletion


def backfill_group_rack(apps, schema_editor):
    """Best-effort: map legacy AR groups to the customer's first rack.

    Existing production-like data did not store the rack on ARGroup. This keeps
    legacy rows usable after migration; operators can correct the location later
    through Edit Tenant where the selected rack is saved on the group.
    """
    ARGroup = apps.get_model('core', 'ARGroup')
    for group in ARGroup.objects.filter(rack__isnull=True).iterator():
        customer = group.customer
        first_rack = customer.racks.order_by('id').first()
        if first_rack:
            group.rack_id = first_rack.id
            group.save(update_fields=['rack'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='argroup',
            name='rack',
            field=models.ForeignKey(
                blank=True,
                db_column='rack_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ar_groups',
                to='core.rack',
            ),
        ),
        migrations.RunPython(backfill_group_rack, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='argroup',
            name='uniq_ar_group_per_customer',
        ),
        migrations.AddConstraint(
            model_name='argroup',
            constraint=models.UniqueConstraint(
                fields=('customer', 'rack', 'validity_AR', 'due_date'),
                name='uniq_ar_group_per_customer_rack',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='ar',
            name='uniq_ar_email_per_customer',
        ),
        migrations.AddConstraint(
            model_name='ar',
            constraint=models.UniqueConstraint(
                fields=('customer', 'ar_group', 'email_address'),
                name='uniq_ar_email_per_customer_group',
            ),
        ),
    ]
