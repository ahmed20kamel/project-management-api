"""
Django signals لتحديث حالة المشروع تلقائياً بناءً على الدفعات
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Payment, Project


@receiver(post_save, sender=Payment)
def update_project_status_on_payment_save(sender, instance, created, **kwargs):
    """تحديث حالة المشروع عند إضافة أو تعديل دفعة"""
    if instance and instance.project_id:
        try:
            # ✅ إعادة تحميل المشروع من قاعدة البيانات
            project = Project.objects.get(pk=instance.project_id)
            # ✅ تحديث الحالة
            project.update_status_from_payments()
        except Project.DoesNotExist:
            pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating project status on payment save: {e}", exc_info=True)


@receiver(post_delete, sender=Payment)
def update_project_status_on_payment_delete(sender, instance, **kwargs):
    """تحديث حالة المشروع عند حذف دفعة"""
    if instance and instance.project_id:
        try:
            # ✅ إعادة تحميل المشروع من قاعدة البيانات
            project = Project.objects.get(pk=instance.project_id)
            # ✅ تحديث الحالة
            project.update_status_from_payments()
        except Project.DoesNotExist:
            pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating project status on payment delete: {e}", exc_info=True)
