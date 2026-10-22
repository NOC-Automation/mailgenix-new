from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0016_changelog_v197")]
    operations = [
        migrations.AlterField(
            model_name="remotehandsattachment",
            name="caption",
            field=models.TextField(blank=True, default=""),
        ),
    ]
