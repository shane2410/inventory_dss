from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_multilevelbomedge"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesdata",
            name="source",
            field=models.CharField(
                choices=[("operations", "Operations"), ("planning", "Planning")],
                db_index=True,
                default="operations",
                max_length=20,
            ),
        ),
    ]
