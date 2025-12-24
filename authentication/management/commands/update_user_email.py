"""
Management command لتغيير email المستخدم
"""
from django.core.management.base import BaseCommand
from authentication.models import User


class Command(BaseCommand):
    help = 'تغيير email المستخدم من ahmed@yafoor.com إلى hayder@alyafour.com'

    def handle(self, *args, **options):
        old_email = 'ahmed@yafoor.com'
        new_email = 'hayder@alyafour.com'
        
        try:
            user = User.objects.get(email=old_email)
            self.stdout.write(f'✅ تم العثور على المستخدم: {user.email}')
            
            # التحقق من أن الـ email الجديد غير مستخدم
            if User.objects.filter(email=new_email).exists():
                self.stdout.write(
                    self.style.ERROR(f'❌ الـ email {new_email} مستخدم بالفعل!')
                )
                return
            
            # تغيير الـ email
            user.email = new_email
            user.username = new_email  # تحديث username أيضاً
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ تم تغيير email المستخدم من {old_email} إلى {new_email}'
                )
            )
            self.stdout.write(f'   - User ID: {user.id}')
            self.stdout.write(f'   - Name: {user.get_full_name()}')
            self.stdout.write(f'   - Tenant: {user.tenant.name if user.tenant else "None"}')
            self.stdout.write(f'   - Is Staff: {user.is_staff}')
            self.stdout.write(f'   - Is Superuser: {user.is_superuser}')
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'⚠️  المستخدم {old_email} غير موجود')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطأ: {e}')
            )

