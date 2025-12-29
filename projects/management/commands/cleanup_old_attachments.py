"""
Management command لحذف المرفقات القديمة وإعادة إنشاء الهيكل الجديد

هذا الأمر يحذف جميع المرفقات القديمة ويقوم بإعادة إنشاء هيكل المجلدات
لجميع المشاريع الموجودة باستخدام النظام الجديد.

المجلدات التي سيتم حذفها:
- awarding/
- contracts/
- licenses/
- owners/
- projects/ (جميع المجلدات القديمة)
- siteplans/

المجلدات التي سيتم الحفاظ عليها:
- tenants/ (لوجوهات الشركات)
- users/ (أفاتار المستخدمين)

الاستخدام:
    python manage.py cleanup_old_attachments --dry-run  # معاينة فقط
    python manage.py cleanup_old_attachments             # تنفيذ فعلي
"""
import os
import shutil
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
from projects.models import Project
from projects.utils import create_project_folder_structure, get_project_folder_name

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'حذف المرفقات القديمة وإعادة إنشاء هيكل المجلدات الجديد لجميع المشاريع'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='معاينة العمليات دون تنفيذها فعلياً',
        )
        parser.add_argument(
            '--keep-projects',
            action='store_true',
            help='الحفاظ على مجلد projects/ القديم (للاسترجاع)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        keep_projects = options.get('keep_projects', False)

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('تنظيف المرفقات القديمة وإعادة إنشاء الهيكل الجديد'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  وضع Dry Run - لن يتم حذف أو إنشاء أي ملفات فعلياً'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  سيتم حذف جميع المرفقات القديمة!'))
        
        # الحصول على MEDIA_ROOT
        media_root = settings.MEDIA_ROOT
        if isinstance(media_root, str):
            media_root = os.path.abspath(media_root)
        else:
            media_root = str(media_root.absolute())
        
        self.stdout.write(f'📂 MEDIA_ROOT: {media_root}')
        
        if not os.path.exists(media_root):
            self.stdout.write(self.style.WARNING(f'⚠️  المجلد {media_root} غير موجود'))
            return
        
        # قائمة المجلدات القديمة التي سيتم حذفها
        old_folders_to_delete = [
            'awarding',
            'contracts',
            'licenses',
            'owners',
            'siteplans',
        ]
        
        # مجلد projects - سيتم معالجته بشكل خاص
        projects_folder = os.path.join(media_root, 'projects')
        
        # ==========================================
        # 1) حذف المجلدات القديمة
        # ==========================================
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('1. حذف المجلدات القديمة'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        deleted_count = 0
        for folder_name in old_folders_to_delete:
            folder_path = os.path.join(media_root, folder_name)
            if os.path.exists(folder_path):
                if dry_run:
                    self.stdout.write(f'   📁 [DRY RUN] سيتم حذف: {folder_name}/')
                    deleted_count += 1
                else:
                    try:
                        if os.path.isdir(folder_path):
                            shutil.rmtree(folder_path)
                            self.stdout.write(self.style.SUCCESS(f'   ✅ تم حذف: {folder_name}/'))
                            deleted_count += 1
                        else:
                            os.remove(folder_path)
                            self.stdout.write(self.style.SUCCESS(f'   ✅ تم حذف: {folder_name}'))
                            deleted_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'   ❌ خطأ في حذف {folder_name}/: {e}'))
                        logger.error(f"Error deleting {folder_path}: {e}", exc_info=True)
            else:
                self.stdout.write(f'   ⏭️  {folder_name}/ غير موجود - تم التخطي')
        
        # حذف مجلد projects القديم
        if os.path.exists(projects_folder):
            if keep_projects:
                # إعادة تسمية المجلد بدلاً من حذفه
                old_projects_backup = os.path.join(media_root, 'projects_old_backup')
                if dry_run:
                    self.stdout.write(f'   📁 [DRY RUN] سيتم إعادة تسمية: projects/ -> projects_old_backup/')
                else:
                    try:
                        if os.path.exists(old_projects_backup):
                            shutil.rmtree(old_projects_backup)
                        os.rename(projects_folder, old_projects_backup)
                        self.stdout.write(self.style.SUCCESS(f'   ✅ تم إعادة تسمية: projects/ -> projects_old_backup/'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'   ❌ خطأ في إعادة تسمية projects/: {e}'))
                        logger.error(f"Error renaming {projects_folder}: {e}", exc_info=True)
            else:
                if dry_run:
                    self.stdout.write(f'   📁 [DRY RUN] سيتم حذف: projects/')
                    deleted_count += 1
                else:
                    try:
                        shutil.rmtree(projects_folder)
                        self.stdout.write(self.style.SUCCESS(f'   ✅ تم حذف: projects/'))
                        deleted_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'   ❌ خطأ في حذف projects/: {e}'))
                        logger.error(f"Error deleting {projects_folder}: {e}", exc_info=True)
        else:
            self.stdout.write(f'   ⏭️  projects/ غير موجود - تم التخطي')
        
        if not dry_run and deleted_count > 0:
            self.stdout.write(self.style.SUCCESS(f'\n✅ تم حذف {deleted_count} مجلد'))
        
        # ==========================================
        # 2) إعادة إنشاء هيكل المجلدات للمشاريع الموجودة
        # ==========================================
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('2. إعادة إنشاء هيكل المجلدات للمشاريع الموجودة'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # جلب جميع المشاريع
        projects = Project.objects.all().order_by('id')
        total_projects = projects.count()
        
        if total_projects == 0:
            self.stdout.write(self.style.WARNING('⚠️  لا توجد مشاريع في قاعدة البيانات'))
        else:
            self.stdout.write(f'📁 عدد المشاريع: {total_projects}')
            
            success_count = 0
            error_count = 0
            
            for idx, project in enumerate(projects, 1):
                project_folder = get_project_folder_name(project)
                project_code = getattr(project, 'internal_code', None) or str(project.id)
                project_name = project.name or f'Project #{project.id}'
                
                self.stdout.write('')
                self.stdout.write(f'[{idx}/{total_projects}] المشروع: {project_name} (ID: {project.id}, Code: {project_code})')
                self.stdout.write(f'   📂 المجلد الجديد: {project_folder}')
                
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'   ⚠️  [DRY RUN] سيتم إنشاء هيكل المجلدات'))
                    success_count += 1
                    continue
                
                try:
                    success = create_project_folder_structure(project)
                    if success:
                        self.stdout.write(self.style.SUCCESS(f'   ✅ تم إنشاء هيكل المجلدات بنجاح'))
                        success_count += 1
                    else:
                        self.stdout.write(self.style.WARNING(f'   ⚠️  فشل إنشاء بعض المجلدات (راجع السجلات)'))
                        error_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ خطأ: {str(e)}'))
                    logger.error(f"Error creating folder structure for project {project.id}: {e}", exc_info=True)
                    error_count += 1
            
            # ملخص النتائج
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('ملخص النتائج:'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(f'✅ نجح: {success_count} مشروع')
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'❌ فشل: {error_count} مشروع'))
        
        # ==========================================
        # ملخص نهائي
        # ==========================================
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  كان هذا Dry Run - لم يتم تنفيذ أي تغييرات'))
            self.stdout.write(self.style.SUCCESS('لتنفيذ التغييرات فعلياً، قم بتشغيل الأمر بدون --dry-run'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ تم الانتهاء من تنظيف المرفقات القديمة وإنشاء الهيكل الجديد'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # تذكير بالحفاظ على tenants و users
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('📌 ملاحظة: تم الحفاظ على المجلدات التالية:'))
        self.stdout.write('   - tenants/ (لوجوهات الشركات)')
        self.stdout.write('   - users/ (أفاتار المستخدمين)')

