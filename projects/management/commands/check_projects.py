"""
Management command للتحقق من وجود المشاريع في قاعدة البيانات
"""
from django.core.management.base import BaseCommand
from projects.models import Project
from authentication.models import Tenant, User


class Command(BaseCommand):
    help = 'التحقق من وجود المشاريع في قاعدة البيانات وعرض إحصائيات'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('🔍 التحقق من البيانات في قاعدة PostgreSQL'))
        self.stdout.write('=' * 60 + '\n')
        
        # ✅ إحصائيات عامة
        total_projects = Project.objects.all().count()
        self.stdout.write(f'📊 إجمالي المشاريع في قاعدة البيانات: {self.style.SUCCESS(str(total_projects))}')
        
        if total_projects == 0:
            self.stdout.write(self.style.WARNING('\n⚠️  لا توجد مشاريع في قاعدة البيانات!'))
            self.stdout.write('   قد تحتاج إلى إنشاء مشاريع جديدة أو استيراد البيانات.')
        else:
            # ✅ عرض المشاريع حسب Tenant
            self.stdout.write('\n📋 المشاريع حسب الشركة (Tenant):')
            self.stdout.write('-' * 60)
            
            tenants = Tenant.objects.all()
            for tenant in tenants:
                tenant_projects = Project.objects.filter(tenant=tenant).count()
                if tenant_projects > 0:
                    self.stdout.write(
                        f'  🏢 {tenant.name} ({tenant.slug}): '
                        f'{self.style.SUCCESS(str(tenant_projects))} مشروع'
                    )
                    
                    # عرض أول 5 مشاريع
                    projects = Project.objects.filter(tenant=tenant)[:5]
                    for project in projects:
                        self.stdout.write(
                            f'     - #{project.id}: {project.name or "بدون اسم"} '
                            f'({project.status})'
                        )
                    if tenant_projects > 5:
                        self.stdout.write(f'     ... و {tenant_projects - 5} مشروع آخر')
            
            # ✅ المشاريع بدون Tenant
            projects_without_tenant = Project.objects.filter(tenant__isnull=True).count()
            if projects_without_tenant > 0:
                self.stdout.write(
                    f'\n  ⚠️  مشاريع بدون Tenant: {self.style.WARNING(str(projects_without_tenant))}'
                )
        
        # ✅ إحصائيات المستخدمين
        self.stdout.write('\n👥 إحصائيات المستخدمين:')
        self.stdout.write('-' * 60)
        total_users = User.objects.all().count()
        users_with_tenant = User.objects.filter(tenant__isnull=False).count()
        self.stdout.write(f'  إجمالي المستخدمين: {total_users}')
        self.stdout.write(f'  مستخدمين مرتبطين بشركة: {users_with_tenant}')
        
        # ✅ إحصائيات Tenants
        self.stdout.write('\n🏢 إحصائيات الشركات (Tenants):')
        self.stdout.write('-' * 60)
        total_tenants = Tenant.objects.all().count()
        self.stdout.write(f'  إجمالي الشركات: {total_tenants}')
        
        if total_tenants > 0:
            for tenant in Tenant.objects.all():
                users_count = User.objects.filter(tenant=tenant).count()
                projects_count = Project.objects.filter(tenant=tenant).count()
                self.stdout.write(
                    f'  - {tenant.name} ({tenant.slug}): '
                    f'{users_count} مستخدم, {projects_count} مشروع'
                )
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ انتهى التحقق من البيانات'))
        self.stdout.write('=' * 60 + '\n')

