from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_v196(apps, schema_editor):
    Changelog = apps.get_model('core', 'Changelog')
    Changelog.objects.get_or_create(
        version='v1.9.6',
        defaults={
            'title': 'Sequence Management',
            'changes': [
                'Added Sequence Management for EQM, ESG, WAF, AVE, RTA, SFR, DAC, SAC, and POC.',
                'Sequence numbers are generated automatically with independent monthly counters by Type + Site + Month + Year.',
                'JKT2 uses site code 2 and JKT3 uses site code 3; counters reset to 001 every month.',
                'Customer selection is sourced from Tenant List and filtered by the selected site.',
                'Added right-side Add Sequence drawer, sequence preview, filters, KPI cards, edit, void, and audit history.',
                'Document Status supports Linked, Printed, Tenant List, and QR Already Sent & Tenant List.',
                'Admin and User roles can create, view, edit, and void sequences. Issued sequence numbers are immutable and never reused.',
                'Approved By is automatically derived from the logged-in account that creates the sequence.',
            ],
            'released_at': django.utils.timezone.localdate(),
            'is_published': True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0012_changelog_v195'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='SequenceCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence_type', models.CharField(max_length=10)),
                ('year', models.PositiveSmallIntegerField()),
                ('month', models.PositiveSmallIntegerField()),
                ('last_value', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sequence_counters', to='core.sitelocation')),
            ],
            options={'db_table': 'sequence_counters'},
        ),
        migrations.CreateModel(
            name='SequenceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence_number', models.CharField(editable=False, max_length=80, unique=True)),
                ('sequence_type', models.CharField(choices=[('EQM','EQM'),('ESG','ESG'),('WAF','WAF'),('AVE','AVE'),('RTA','RTA'),('SFR','SFR'),('DAC','DAC'),('SAC','SAC'),('POC','POC')], editable=False, max_length=10)),
                ('activity', models.CharField(max_length=40)),
                ('ticket_number', models.CharField(blank=True, default='', max_length=120)),
                ('document_status', models.CharField(choices=[('Linked','Linked'),('Printed','Printed'),('Tenant List','Tenant List'),('QR Already Sent & Tenant List','QR Already Sent & Tenant List')], default='Linked', max_length=60)),
                ('eqm_saved', models.BooleanField(blank=True, null=True)),
                ('operational_date', models.DateField()),
                ('remarks', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(choices=[('Active','Active'),('Void','Void')], default='Active', max_length=20)),
                ('void_reason', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='sequences_created', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sequences_updated', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sequences', to='core.customers')),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sequences', to='core.sitelocation')),
            ],
            options={'db_table': 'sequence_records', 'ordering': ['-operational_date', '-id']},
        ),
        migrations.CreateModel(
            name='SequenceAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('create','Create'),('update','Update'),('void','Void')], max_length=20)),
                ('field_changed', models.CharField(blank=True, default='', max_length=80)),
                ('old_value', models.TextField(blank=True, default='')),
                ('new_value', models.TextField(blank=True, default='')),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('sequence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='core.sequencerecord')),
            ],
            options={'db_table': 'sequence_audit_logs', 'ordering': ['-changed_at', '-id']},
        ),
        migrations.AddConstraint(model_name='sequencecounter', constraint=models.UniqueConstraint(fields=('sequence_type','site','year','month'), name='uniq_sequence_counter_scope')),
        migrations.AddIndex(model_name='sequencerecord', index=models.Index(fields=['sequence_type','site','operational_date'], name='sequence_re_seq_typ_f03147_idx')),
        migrations.AddIndex(model_name='sequencerecord', index=models.Index(fields=['status'], name='sequence_re_status_74a9c1_idx')),
        migrations.AddIndex(model_name='sequencerecord', index=models.Index(fields=['document_status'], name='sequence_re_documen_442f76_idx')),
        migrations.AddIndex(model_name='sequencerecord', index=models.Index(fields=['ticket_number'], name='sequence_re_ticket__b8e9cf_idx')),
        migrations.AddIndex(model_name='sequenceauditlog', index=models.Index(fields=['sequence','changed_at'], name='sequence_au_sequenc_575dd4_idx')),
        migrations.RunPython(seed_v196, migrations.RunPython.noop),
    ]
