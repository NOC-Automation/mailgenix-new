from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_checklists(apps, schema_editor):
    D = apps.get_model("core", "ChecklistDefinition")
    definitions = [
        dict(site="JKT2", code="jkt2-key-rack", name="Checklist Key Rack", category="Key Rack", schedule_config={"frequency":"daily"}, items=["Key Rack 0001 (UNIVERSAL KEY)","Key Rack 0002 (MANULIFE)","Key Rack 0003 (GELI)","Key Rack 0004 (Dewata Telematika)","Key Rack 0005 (HYPERNET)","Key Rack 0006 (TRANSINDO)","Key Rack 0007 (CNAF)","Key Rack 0008 (A100 STORAGE ROOM)","Key Rack 009 (Toilet B1)","Key 0010 (TOKAI RUBER)","Key 0019 (Key Non Full Rack Master Key)","Key Rack 0011 (Manulife)","Key Rack 012 (Manulife)","Key Rack 0020 (Key Side Rack All Rack)","Key Rack 0021 (Key Summitmas)","Key 0022 (BOND)","Key 0023 (GEGI)"]),
        dict(site="JKT2", code="jkt2-rack-colo", name="Checklist Rack COLO at Data Center NTT Indonesia JKT2", category="Rack COLO", schedule_config={"frequency":"daily"}, items=["L1.SVR1 (Collocation)","L1.SVR02 (Collocation)","L2.SVR02 (Share Cage)","L3.SVR03 (Collocation)","L6.SVR01 (Collocation)","L8.SVR02 (Collocation)"]),
        dict(site="JKT2", code="jkt2-bond-video", name="PATROL BOND - Video Patrol", category="PATROL BOND", schedule_config={"shifts":{"A":["09:30","13:30"],"A3":["17:30","21:30"],"A2":["09:30","13:30","17:30"],"B3":["01:30","05:30"],"B1":["21:30","01:30","05:30"]}}, items=["CCTV BOND JKT32","CCTV BOND JKT34","CCTV BOND Storage"]),
        dict(site="JKT2", code="jkt2-bond-in-person", name="PATROL BOND - In Person Patrol", category="PATROL BOND", schedule_config={"evidence_required":True,"shifts":{"A":["09:30"],"A3":["17:30"],"A2":["09:30","17:30"],"B3":["01:30"],"B1":["01:30"]}}, items=["Check RPDU Status","Check Sensor","Check Active Devices","Check Cold Air Flow","Check CAC Door"]),
        dict(site="JKT2", code="jkt2-mizuho-daily", name="Mizuho Daily Checklist", category="Daily Checklist", schedule_config={"required_shifts":["A3","B1"]}, items=["LAMP","Monthly CO2 Fire Extinguisher - 3.5 Kg","Monthly CO2 Fire Extinguisher - 6.8 Kg"]),
        dict(site="JKT3", code="jkt3-patrol-key-rack", name="Checklist Patrol and Key Rack", category="Patrol & Key Rack", schedule_config={"frequency":"daily"}, items=["L1.DH01","L1.DH02"]),
    ]
    for row in definitions:
        code=row["code"]
        defaults={k:v for k,v in row.items() if k!="code"}
        D.objects.update_or_create(code=code, defaults=defaults)


def refresh_support_status(apps, schema_editor):
    SupportGroup=apps.get_model("core","SupportGroup")
    today=django.utils.timezone.localdate()
    for item in SupportGroup.objects.all().iterator():
        if item.validity_date:
            days=(item.validity_date-today).days
            status="Expired" if days < 0 else ("Expiring Soon" if days <= 30 else "Active")
        else:
            status="Active"
        if item.status != status:
            item.status=status; item.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies=[("core","0013_sequence_management_v196"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name="mailinggroup", name="specific_customers", field=models.ManyToManyField(blank=True, related_name="explicit_mailing_groups", to="core.customers")),
        migrations.AlterField(model_name="supportgroup", name="status", field=models.CharField(choices=[("Active","Active"),("Expiring Soon","Expiring Soon"),("Expired","Expired")], default="Active", max_length=20)),
        migrations.CreateModel(name="CustomerAssociation", fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("association_type",models.CharField(choices=[("contractor_waf","Contractor / WAF"),("visitor_ave","Visitor / AVE")],max_length=30)),("name",models.CharField(max_length=255)),("identity_number",models.CharField(blank=True,default="",max_length=255)),("access_level",models.CharField(blank=True,default="",max_length=255)),("email_phone",models.CharField(blank=True,default="",max_length=255)),("reference_info",models.CharField(blank=True,default="",max_length=255)),("notes",models.CharField(blank=True,default="",max_length=255)),("validity_date",models.DateField(blank=True,null=True)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("customer",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="associations",to="core.customers")),("rack",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="customer_associations",to="core.rack"))], options={"db_table":"customer_associations","ordering":["customer_id","association_type","name"]}),
        migrations.CreateModel(name="ChecklistDefinition", fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("site",models.CharField(choices=[("JKT2","JKT2"),("JKT3","JKT3")],max_length=10)),("code",models.SlugField(max_length=80,unique=True)),("name",models.CharField(max_length=255)),("category",models.CharField(blank=True,default="",max_length=80)),("schedule_config",models.JSONField(blank=True,default=dict)),("items",models.JSONField(blank=True,default=list)),("active",models.BooleanField(default=True)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True))], options={"db_table":"checklist_definitions","ordering":["site","name"]}),
        migrations.CreateModel(name="ChecklistSubmission", fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("operational_date",models.DateField(default=django.utils.timezone.localdate)),("shift",models.CharField(max_length=20)),("site",models.CharField(max_length=10)),("status",models.CharField(choices=[("Draft","Draft"),("Completed","Completed"),("Incomplete","Incomplete")],default="Draft",max_length=20)),("answers",models.JSONField(blank=True,default=dict)),("is_backdated",models.BooleanField(default=False)),("created_at",models.DateTimeField(auto_now_add=True)),("completed_at",models.DateTimeField(blank=True,null=True)),("updated_at",models.DateTimeField(auto_now=True)),("definition",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="submissions",to="core.checklistdefinition")),("pic",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="checklist_submissions",to=settings.AUTH_USER_MODEL))], options={"db_table":"checklist_submissions","ordering":["-operational_date","-created_at"]}),
        migrations.AddConstraint(model_name="checklistsubmission", constraint=models.UniqueConstraint(fields=("definition","operational_date","shift"),name="uniq_checklist_definition_date_shift")),
        migrations.CreateModel(name="ChecklistEvidence", fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("schedule_time",models.CharField(blank=True,default="",max_length=10)),("file",models.FileField(upload_to="checklist_evidence/%Y/%m/")),("uploaded_at",models.DateTimeField(auto_now_add=True)),("submission",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="evidence_files",to="core.checklistsubmission")),("uploaded_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))], options={"db_table":"checklist_evidence"}),
        migrations.RunPython(refresh_support_status, migrations.RunPython.noop),
        migrations.RunPython(seed_checklists, migrations.RunPython.noop),
    ]
