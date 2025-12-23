"""
Management command لتحديث حالة جميع المشاريع بناءً على الدفعات
"""
from django.core.management.base import BaseCommand
from projects.models import Project


class Command(BaseCommand):
    help = 'تحديث حالة جميع المشاريع بناءً على الدفعات الحالية'

    def handle(self, *args, **options):
        projects = Project.objects.all()
        total = projects.count()
        updated = 0
        errors = 0
        
        self.stdout.write(f'🔍 جاري تحديث حالة {total} مشروع...\n')
        
        for project in projects:
            try:
                old_status = project.status
                # ✅ إعادة تحميل المشروع من قاعدة البيانات
                project.refresh_from_db()
                # ✅ حساب الحالة الجديدة
                new_status = project.calculate_status_from_payments()
                
                if old_status != new_status:
                    # ✅ تحديث الحالة
                    Project.objects.filter(pk=project.pk).update(status=new_status)
                    updated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ المشروع #{project.id}: "{old_status}" → "{new_status}"'
                        )
                    )
                else:
                    self.stdout.write(
                        f'ℹ️  المشروع #{project.id}: الحالة "{project.status}" (لم تتغير)'
                    )
            except Exception as e:
                errors += 1
                import traceback
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ خطأ في المشروع #{project.id}: {e}'
                    )
                )
                self.stdout.write(traceback.format_exc())
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ تم تحديث {updated} من {total} مشروع'
            )
        )
        if errors > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ {errors} أخطاء')
            )
        self.stdout.write('=' * 50)
