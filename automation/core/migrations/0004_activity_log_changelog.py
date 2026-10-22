from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from datetime import timedelta
from django.conf import settings


def seed_changelog(apps, schema_editor):
    Changelog = apps.get_model('core', 'Changelog')
    entries = [
        ('v1.5.0', 'Operational audit & dashboard', [
            'Added Activity Log visible to all authenticated users',
            'Added Changelog / What\'s New panel',
            'Logged generated Outlook notification drafts',
            'Added dashboard validity and Support Group summaries',
            'Corrected bulk Mailing List Group recipients to BCC',
        ]),
        ('v1.4.0', 'Customer workspace & Support Group', [
            'Added Support Group CRUD',
            'Added customer Active / Expiring Soon / Expired status',
            'Added customer-centric Tenant List workspace',
            'Added Support Group dashboard counts',
        ]),
        ('v1.3.0', 'Location-aware recipients', [
            'Authorized Person can differ by site, floor, and rack',
            'Specific Customer resolves matching location ARs to TO',
            'Site/Floor bulk resolves matching location ARs to BCC',
            'Improved recipient deduplication',
        ]),
        ('v1.2.0', 'Notification workflow', [
            'Added notification template gallery and preview',
            'Added Outlook .eml draft generation',
            'Embedded email images using CID',
            'Added dynamic Authorized Person rows',
        ]),
    ]
    today = django.utils.timezone.localdate()
    for idx, (version, title, changes) in enumerate(entries):
        Changelog.objects.get_or_create(
            version=version,
            defaults={'title': title, 'changes': changes, 'released_at': today - timedelta(days=idx*14), 'is_published': True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_support_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('create','Create'),('update','Update'),('delete','Delete'),('import','Import'),('generate_notification','Generate Notification'),('login','Login'),('other','Other')], default='other', max_length=40)),
                ('entity_type', models.CharField(blank=True, default='', max_length=80)),
                ('entity_id', models.CharField(blank=True, default='', max_length=80)),
                ('entity_label', models.CharField(blank=True, default='', max_length=255)),
                ('description', models.CharField(blank=True, default='', max_length=500)),
                ('status', models.CharField(default='success', max_length=30)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table':'activity_logs','ordering':['-created_at','-id']},
        ),
        migrations.CreateModel(
            name='Changelog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=40)),
                ('title', models.CharField(blank=True, default='', max_length=255)),
                ('changes', models.JSONField(blank=True, default=list)),
                ('released_at', models.DateField(default=django.utils.timezone.localdate)),
                ('is_published', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table':'app_changelog','ordering':['-released_at','-id']},
        ),
        migrations.AddIndex(model_name='activitylog', index=models.Index(fields=['created_at'], name='activity_lo_created_4db17e_idx')),
        migrations.AddIndex(model_name='activitylog', index=models.Index(fields=['action'], name='activity_lo_action_c6533b_idx')),
        migrations.AddIndex(model_name='activitylog', index=models.Index(fields=['entity_type'], name='activity_lo_entity__2bd630_idx')),
        migrations.RunPython(seed_changelog, migrations.RunPython.noop),
    ]
