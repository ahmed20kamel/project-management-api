"""
Management command لإصلاح جدول الدفعات
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'إصلاح جدول الدفعات - إنشاء الجدول إذا لم يكن موجوداً'

    def handle(self, *args, **options):
        cursor = connection.cursor()
        
        # التحقق من وجود الجدول
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='projects_payment'
        """)
        table_exists = cursor.fetchone()
        
        if table_exists:
            self.stdout.write(
                self.style.SUCCESS('✅ الجدول موجود بالفعل!')
            )
            return
        
        self.stdout.write('🔨 إنشاء جدول projects_payment...')
        
        try:
            # إنشاء الجدول
            cursor.execute("""
                CREATE TABLE projects_payment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    amount DECIMAL(14, 2) NOT NULL,
                    date DATE NOT NULL,
                    description TEXT NOT NULL,
                    project_id INTEGER NULL,
                    FOREIGN KEY (project_id) REFERENCES projects_project (id) ON DELETE CASCADE
                )
            """)
            
            # إنشاء index
            cursor.execute("""
                CREATE INDEX projects_payment_project_id_idx 
                ON projects_payment(project_id)
            """)
            
            connection.commit()
            self.stdout.write(
                self.style.SUCCESS('✅ تم إنشاء الجدول بنجاح!')
            )
            
            # التحقق من migration
            cursor.execute("""
                SELECT * FROM django_migrations 
                WHERE app='projects' AND name='0016_payment'
            """)
            migration_exists = cursor.fetchone()
            
            if not migration_exists:
                # تسجيل migration
                now = timezone.now()
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('projects', '0016_payment', ?)
                """, (now,))
                connection.commit()
                self.stdout.write(
                    self.style.SUCCESS('✅ تم تسجيل migration')
                )
            else:
                self.stdout.write('ℹ️  Migration مسجلة بالفعل')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطأ: {e}')
            )
            import traceback
            traceback.print_exc()
            return
        
        # التحقق النهائي
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='projects_payment'
        """)
        final_check = cursor.fetchone()
        
        if final_check:
            self.stdout.write(
                self.style.SUCCESS('\n✅ كل شيء جاهز! الجدول موجود ويمكن استخدامه.')
            )
        else:
            self.stdout.write(
                self.style.ERROR('\n❌ فشل إنشاء الجدول!')
            )
