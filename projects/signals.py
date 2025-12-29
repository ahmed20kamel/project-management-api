"""
Django signals لتحديث حالة المشروع تلقائياً بناءً على الدفعات
وإنشاء هيكل المجلدات للمشاريع الجديدة
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Payment, Project, SitePlan, SitePlanOwner
from .utils import create_project_folder_structure, get_project_folder_name
from django.core.files.storage import default_storage
import os

logger = logging.getLogger(__name__)


# حفظ الاسم القديم قبل التحديث
_project_name_cache = {}


@receiver(pre_save, sender=Project)
def cache_old_project_name(sender, instance, **kwargs):
    """حفظ الاسم القديم للمشروع قبل التحديث"""
    if instance.pk:
        try:
            old_instance = Project.objects.get(pk=instance.pk)
            _project_name_cache[instance.pk] = old_instance.name
        except Project.DoesNotExist:
            pass


@receiver(post_save, sender=Project)
def create_project_folder_structure_on_create(sender, instance, created, **kwargs):
    """
    لا ننشئ المجلد عند إنشاء المشروع مباشرة
    سيتم إنشاء المجلد عندما يتم إضافة SitePlan مع owners
    """
    # تم تعطيل إنشاء المجلد هنا لمنع إنشاء مجلدين
    # سيتم إنشاء المجلد في signal الخاص بـ SitePlan
    pass


@receiver(post_save, sender=SitePlan)
def create_project_folder_on_siteplan_create(sender, instance, created, **kwargs):
    """
    إنشاء هيكل المجلدات عند إنشاء SitePlan
    هذا يضمن أن المجلد يُنشأ مرة واحدة فقط عندما يكون هناك owners
    """
    if created and instance and instance.project_id:
        try:
            # التحقق من وجود owners
            owners_count = SitePlanOwner.objects.filter(siteplan=instance).count()
            if owners_count > 0:
                logger.info(f"📁 Creating folder structure for project {instance.project_id} after SitePlan creation with owners")
                success = create_project_folder_structure(instance.project)
                if success:
                    logger.info(f"✅ Successfully created folder structure for project {instance.project_id}")
                else:
                    logger.warning(f"⚠️ Failed to create folder structure for project {instance.project_id}")
        except Exception as e:
            logger.error(f"❌ Error creating folder structure for project {instance.project_id}: {e}", exc_info=True)


@receiver(post_save, sender=SitePlanOwner)
def ensure_project_folder_on_owner_create(sender, instance, created, **kwargs):
    """
    التأكد من وجود هيكل المجلدات عند إضافة owner جديد
    """
    if created and instance and instance.siteplan and instance.siteplan.project_id:
        try:
            project = instance.siteplan.project
            # التحقق من وجود المجلد
            project_folder = get_project_folder_name(project)
            folder_path = f'projects/{project_folder}'
            
            # التحقق من وجود المجلد
            try:
                listdir_result = default_storage.listdir(folder_path)
                folder_exists = True
            except (OSError, FileNotFoundError):
                folder_exists = False
            
            if not folder_exists:
                # المجلد غير موجود - إنشاؤه
                logger.info(f"📁 Creating folder structure for project {project.id} after adding owner")
                success = create_project_folder_structure(project)
                if success:
                    logger.info(f"✅ Successfully created folder structure for project {project.id}")
        except Exception as e:
            logger.debug(f"Error checking folder structure for project {instance.siteplan.project_id}: {e}")


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
            logger.error(f"Error updating project status on payment delete: {e}", exc_info=True)
