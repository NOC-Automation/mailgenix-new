from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0002_location_scoped_ar_groups")]

    operations = [
        migrations.CreateModel(
            name="SupportGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("identity_number", models.CharField(blank=True, default="", max_length=255)),
                ("access_level", models.CharField(blank=True, default="", max_length=255)),
                ("email_phone", models.CharField(blank=True, default="", max_length=255)),
                ("reference_info", models.CharField(blank=True, default="", max_length=255)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("validity_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("Active", "Active"), ("Expired", "Expired")], default="Active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(db_column="customer_id", on_delete=django.db.models.deletion.CASCADE, related_name="support_groups", to="core.customers")),
                ("rack", models.ForeignKey(blank=True, db_column="rack_id", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="support_groups", to="core.rack")),
            ],
            options={"db_table": "support_groups", "ordering": ["customer_id", "name", "id"]},
        ),
        migrations.AddIndex(model_name="supportgroup", index=models.Index(fields=["customer", "status"], name="support_gro_custome_75327c_idx")),
        migrations.AddIndex(model_name="supportgroup", index=models.Index(fields=["validity_date"], name="support_gro_validit_c82930_idx")),
    ]
