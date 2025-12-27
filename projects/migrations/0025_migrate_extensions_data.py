# Generated manually to migrate extensions data from Contract to StartOrder

from django.db import migrations


def migrate_extensions_data_forward(apps, schema_editor):
    """نقل extensions من Contract إلى StartOrder"""
    Contract = apps.get_model('projects', 'Contract')
    StartOrder = apps.get_model('projects', 'StartOrder')
    
    # ✅ نقل extensions من كل Contract إلى StartOrder المقابل (إن وجد)
    for contract in Contract.objects.all():
        if hasattr(contract, 'extensions') and contract.extensions:
            try:
                # ✅ البحث عن StartOrder المقابل
                start_order = StartOrder.objects.filter(project=contract.project).first()
                if start_order:
                    # ✅ نقل extensions
                    start_order.extensions = contract.extensions
                    start_order.save(update_fields=['extensions'])
            except Exception as e:
                # ✅ في حالة الخطأ، نكمل بدون إيقاف migration
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error migrating extensions for contract {contract.id}: {e}")


def migrate_extensions_data_backward(apps, schema_editor):
    """استرجاع extensions من StartOrder إلى Contract (reverse migration)"""
    Contract = apps.get_model('projects', 'Contract')
    StartOrder = apps.get_model('projects', 'StartOrder')
    
    # ✅ استرجاع extensions من كل StartOrder إلى Contract المقابل
    for start_order in StartOrder.objects.all():
        if hasattr(start_order, 'extensions') and start_order.extensions:
            try:
                # ✅ البحث عن Contract المقابل
                contract = Contract.objects.filter(project=start_order.project).first()
                if contract:
                    # ✅ استرجاع extensions
                    contract.extensions = start_order.extensions
                    contract.save(update_fields=['extensions'])
            except Exception as e:
                # ✅ في حالة الخطأ، نكمل بدون إيقاف migration
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error reverse migrating extensions for start_order {start_order.id}: {e}")


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0024_move_extensions_to_startorder'),
    ]

    operations = [
        migrations.RunPython(
            migrate_extensions_data_forward,
            reverse_code=migrate_extensions_data_backward
        ),
    ]

