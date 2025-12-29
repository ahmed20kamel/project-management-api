"""
Management command لإنشاء هيكل المجلدات للمشاريع القديمة

يتم استخدام هذا الأمر لإنشاء هيكل المجلدات الكامل لجميع المشاريع الموجودة
في النظام، دون حذف أو نقل الملفات الحالية.

الاستخدام:
    python manage.py create_project_folders
    
    # إنشاء الهيكل لمشروع محدد
    python manage.py create_project_folders --project-id 123
    
    # إنشاء الهيكل لجميع المشاريع (افتراضي)
    python manage.py create_project_folders --all
"""
from django.core.management.base import BaseCommand
from projects.models import Project
from projects.utils import create_project_folder_structure
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'إنشاء هيكل المجلدات الكامل للمشاريع الموجودة (القديمة والجديدة)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=int,
            help='إنشاء الهيكل لمشروع محدد فقط (استخدم ID المشروع)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='إنشاء الهيكل لجميع المشاريع (افتراضي)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='عرض المشاريع التي سيتم معالجتها دون إنشاء المجلدات فعلياً',
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        all_projects = options.get('all', True)  # افتراضي: جميع المشاريع
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('إنشاء هيكل المجلدات للمشاريع'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  وضع Dry Run - لن يتم إنشاء المجلدات فعلياً'))

        # تحديد المشاريع المراد معالجتها
        if project_id:
            try:
                project_obj = Project.objects.get(pk=project_id)
                projects = [project_obj]
                self.stdout.write(f'📁 معالجة مشروع واحد: ID={project_id}')
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ المشروع {project_id} غير موجود'))
                return
        else:
            # جميع المشاريع
            projects = list(Project.objects.all().order_by('id'))
            count = len(projects)
            self.stdout.write(f'📁 معالجة {count} مشروع')

        if not projects:
            self.stdout.write(self.style.WARNING('⚠️  لا توجد مشاريع للمعالجة'))
            return

        # معالجة كل مشروع
        success_count = 0
        error_count = 0
        skipped_count = 0

        total_projects = len(projects)
        for idx, project in enumerate(projects, 1):
            project_name = project.name or f"Project #{project.id}"
            project_folder = f"project_{project.id}_{project.name or 'unnamed'}"
            
            self.stdout.write('')
            self.stdout.write(f'[{idx}/{total_projects}] معالجة: {project_name} (ID: {project.id})')
            self.stdout.write(f'   📂 المجلد: {project_folder}')

            if dry_run:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Dry Run: سيتم إنشاء هيكل المجلدات لهذا المشروع'))
                success_count += 1
                continue

            try:
                # إنشاء هيكل المجلدات
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
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ملخص النتائج:'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'✅ نجح: {success_count} مشروع')
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ فشل: {error_count} مشروع'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'⏭️  تم التخطي: {skipped_count} مشروع'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('⚠️  كان هذا Dry Run - لم يتم إنشاء المجلدات فعلياً'))
            self.stdout.write(self.style.SUCCESS('لإنشاء المجلدات فعلياً، قم بتشغيل الأمر بدون --dry-run'))

