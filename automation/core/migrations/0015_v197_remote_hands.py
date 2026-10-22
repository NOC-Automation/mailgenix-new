from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    dependencies=[('core','0014_v197_operational_refinement')]
    operations=[
        migrations.CreateModel(name='RemoteHandsReport', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('report_type',models.CharField(choices=[('Remote Hands Report','Remote Hands Report'),('Custom Remote Hands Report','Custom Remote Hands Report')],default='Remote Hands Report',max_length=80)),
            ('ticket_number',models.CharField(max_length=120)),('site',models.CharField(choices=[('JKT2','JKT2'),('JKT3','JKT3')],max_length=10)),
            ('start_datetime',models.DateTimeField()),('finish_datetime',models.DateTimeField()),('additional_datetime',models.DateTimeField(blank=True,null=True)),
            ('engineer',models.CharField(max_length=255)),('request_by',models.CharField(blank=True,default='',max_length=255)),('shift_leader',models.CharField(blank=True,default='',max_length=255)),
            ('rack_number',models.CharField(blank=True,default='',max_length=255)),('task_detail',models.TextField()),('result_information',models.TextField(blank=True,default='')),
            ('status',models.CharField(choices=[('Draft','Draft'),('Completed','Completed')],default='Draft',max_length=20)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='remote_hands_reports_created',to=settings.AUTH_USER_MODEL)),
            ('customer',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='remote_hands_reports',to='core.customers')),
        ], options={'db_table':'remote_hands_reports','ordering':['-start_datetime','-id']}),
        migrations.CreateModel(name='RemoteHandsAttachment',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('file',models.FileField(upload_to='remote_hands/%Y/%m/')),('caption',models.CharField(blank=True,default='',max_length=255)),('uploaded_at',models.DateTimeField(auto_now_add=True)),
            ('report',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='attachments',to='core.remotehandsreport')),
        ],options={'db_table':'remote_hands_attachments'}),
    ]
