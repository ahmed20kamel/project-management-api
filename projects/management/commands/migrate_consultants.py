"""
Management command لتحويل بيانات الاستشاريين من BuildingLicense إلى Consultant model الجديد
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from projects.models import Consultant, BuildingLicense, Project, ProjectConsultant


class Command(BaseCommand):
    help = 'تحويل بيانات الاستشاريين من BuildingLicense إلى Consultant model الجديد'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='عرض ما سيتم عمله بدون حفظ في قاعدة البيانات',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Dry run mode - لن يتم حفظ أي تغييرات'))
        
        consultants_created = 0
        project_consultants_created = 0
        licenses_updated = 0
        
        # جلب جميع التراخيص التي تحتوي على بيانات استشاريين
        licenses = BuildingLicense.objects.select_related('project', 'project__tenant').all()
        
        self.stdout.write(f'📋 تم العثور على {licenses.count()} رخصة بناء')
        
        with transaction.atomic():
            consultants_map = {}  # لتجنب تكرار الاستشاريين
            
            for license in licenses:
                if not license.project or not license.project.tenant:
                    continue
                
                tenant = license.project.tenant
                
                # معالجة استشاري التصميم
                if license.design_consultant_name:
                    consultant_key = (
                        tenant.id,
                        license.design_consultant_name.strip().lower(),
                        (license.design_consultant_license_no or '').strip()
                    )
                    
                    if consultant_key not in consultants_map:
                        # إنشاء أو جلب الاستشاري
                        consultant, created = Consultant.objects.get_or_create(
                            tenant=tenant,
                            name=license.design_consultant_name.strip(),
                            license_no=(license.design_consultant_license_no or '').strip(),
                            defaults={
                                'name_en': (license.design_consultant_name_en or '').strip(),
                            }
                        )
                        
                        if created:
                            consultants_created += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ تم إنشاء استشاري: {consultant.name}')
                            )
                        
                        consultants_map[consultant_key] = consultant
                    else:
                        consultant = consultants_map[consultant_key]
                        # تحديث name_en إذا كان موجوداً في الرخصة وليس موجوداً في الاستشاري
                        if license.design_consultant_name_en and not consultant.name_en:
                            consultant.name_en = license.design_consultant_name_en.strip()
                            if not dry_run:
                                consultant.save(update_fields=['name_en'])
                    
                    # ربط الاستشاري بالمشروع كاستشاري تصميم
                    if not dry_run:
                        project_consultant, created = ProjectConsultant.objects.get_or_create(
                            project=license.project,
                            consultant=consultant,
                            role='design',
                            defaults={}
                        )
                        if created:
                            project_consultants_created += 1
                    
                    # تحديث الرخصة لاستخدام Consultant الجديد
                    if not dry_run and not license.design_consultant:
                        license.design_consultant = consultant
                        license.save(update_fields=['design_consultant'])
                        licenses_updated += 1
                
                # معالجة استشاري الإشراف (إذا كان مختلف عن التصميم)
                if (license.supervision_consultant_name and 
                    license.supervision_consultant_name != license.design_consultant_name):
                    
                    consultant_key = (
                        tenant.id,
                        license.supervision_consultant_name.strip().lower(),
                        (license.supervision_consultant_license_no or '').strip()
                    )
                    
                    if consultant_key not in consultants_map:
                        # إنشاء أو جلب الاستشاري
                        consultant, created = Consultant.objects.get_or_create(
                            tenant=tenant,
                            name=license.supervision_consultant_name.strip(),
                            license_no=(license.supervision_consultant_license_no or '').strip(),
                            defaults={
                                'name_en': (license.supervision_consultant_name_en or '').strip(),
                            }
                        )
                        
                        if created:
                            consultants_created += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ تم إنشاء استشاري: {consultant.name}')
                            )
                        
                        consultants_map[consultant_key] = consultant
                    else:
                        consultant = consultants_map[consultant_key]
                        # تحديث name_en إذا كان موجوداً في الرخصة وليس موجوداً في الاستشاري
                        if license.supervision_consultant_name_en and not consultant.name_en:
                            consultant.name_en = license.supervision_consultant_name_en.strip()
                            if not dry_run:
                                consultant.save(update_fields=['name_en'])
                    
                    # ربط الاستشاري بالمشروع كاستشاري إشراف
                    if not dry_run:
                        project_consultant, created = ProjectConsultant.objects.get_or_create(
                            project=license.project,
                            consultant=consultant,
                            role='supervision',
                            defaults={}
                        )
                        if created:
                            project_consultants_created += 1
                    
                    # تحديث الرخصة لاستخدام Consultant الجديد
                    if not dry_run and not license.supervision_consultant:
                        license.supervision_consultant = consultant
                        license.save(update_fields=['supervision_consultant'])
                        licenses_updated += 1
                
                # إذا كان نفس الاستشاري للتصميم والإشراف
                elif (license.consultant_same and 
                      license.design_consultant_name and 
                      license.design_consultant_name == license.supervision_consultant_name):
                    
                    consultant_key = (
                        tenant.id,
                        license.design_consultant_name.strip().lower(),
                        (license.design_consultant_license_no or '').strip()
                    )
                    
                    if consultant_key in consultants_map:
                        consultant = consultants_map[consultant_key]
                        
                        # ربط الاستشاري بالمشروع كاستشاري إشراف أيضاً
                        if not dry_run:
                            project_consultant, created = ProjectConsultant.objects.get_or_create(
                                project=license.project,
                                consultant=consultant,
                                role='supervision',
                                defaults={}
                            )
                            if created:
                                project_consultants_created += 1
                        
                        # تحديث الرخصة
                        if not dry_run and not license.supervision_consultant:
                            license.supervision_consultant = consultant
                            license.save(update_fields=['supervision_consultant'])
                            licenses_updated += 1
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\n⚠️  Dry run - لم يتم حفظ أي تغييرات'))
                self.stdout.write(f'📊 الإحصائيات المتوقعة:')
                self.stdout.write(f'   - استشاريين سيتم إنشاؤهم: {consultants_created}')
                self.stdout.write(f'   - روابط مشاريع سيتم إنشاؤها: {project_consultants_created}')
                self.stdout.write(f'   - تراخيص سيتم تحديثها: {licenses_updated}')
            else:
                self.stdout.write(self.style.SUCCESS('\n✅ تم الانتهاء بنجاح!'))
                self.stdout.write(f'📊 الإحصائيات:')
                self.stdout.write(f'   - استشاريين تم إنشاؤهم: {consultants_created}')
                self.stdout.write(f'   - روابط مشاريع تم إنشاؤها: {project_consultants_created}')
                self.stdout.write(f'   - تراخيص تم تحديثها: {licenses_updated}')

