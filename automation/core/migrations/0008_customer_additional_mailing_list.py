from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def migrate_email_like_legacy_mailing_lists(apps, schema_editor):
    AR = apps.get_model('core', 'AR')
    CustomerAdditionalMailingList = apps.get_model('core', 'CustomerAdditionalMailingList')

    for ar in AR.objects.select_related('customer').prefetch_related('mailing_lists').iterator(chunk_size=500):
        if not ar.customer_id:
            continue
        for legacy in ar.mailing_lists.all():
            email = (legacy.name or '').strip().lower()
            if not email:
                continue
            try:
                validate_email(email)
            except ValidationError:
                # Old v1.8 allowed free-text tags such as "Facility Update".
                # Only actual email addresses are promoted to customer-level recipient lists.
                continue
            CustomerAdditionalMailingList.objects.get_or_create(
                customer_id=ar.customer_id,
                email_address=email,
            )


class Migration(migrations.Migration):
    dependencies = [("core", "0007_changelog_v18")]

    operations = [
        migrations.CreateModel(
            name="CustomerAdditionalMailingList",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_address", models.EmailField(max_length=255)),
                ("label", models.CharField(blank=True, default="", max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(db_column="customer_id", on_delete=django.db.models.deletion.CASCADE, related_name="additional_mailing_lists", to="core.customers")),
            ],
            options={"db_table": "customer_additional_mailing_lists", "ordering": ["customer__name_customer", "email_address"]},
        ),
        migrations.AddConstraint(
            model_name="customeradditionalmailinglist",
            constraint=models.UniqueConstraint(fields=("customer", "email_address"), name="uniq_customer_additional_mailing_email"),
        ),
        migrations.RunPython(migrate_email_like_legacy_mailing_lists, migrations.RunPython.noop),
    ]
