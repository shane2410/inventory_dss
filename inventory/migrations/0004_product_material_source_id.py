# Generated manually to add source IDs from the workbook data.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_alter_transaction_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='source_id',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='material',
            name='source_id',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]