# Generated manually to remove extensions field from Contract after data migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0025_migrate_extensions_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='contract',
            name='extensions',
        ),
    ]

