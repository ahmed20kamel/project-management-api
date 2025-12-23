# Generated manually to add items field to invoices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='initialinvoice',
            name='items',
            field=models.JSONField(blank=True, default=list, help_text='Invoice items: [{description, quantity, unit_price, total}]'),
        ),
        migrations.AddField(
            model_name='actualinvoice',
            name='items',
            field=models.JSONField(blank=True, default=list, help_text='Invoice items: [{description, quantity, unit_price, total}]'),
        ),
    ]

