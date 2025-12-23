from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from decimal import Decimal

# ====== أساس timestamps ======
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Multi-Tenant: ربط جميع النماذج بالشركة (Tenant)
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        null=True,
        blank=True,
        db_index=True,
        help_text="الشركة التي ينتمي إليها هذا السجل"
    )

    class Meta:
        abstract = True


# ====== المشروع ======
class Project(TimeStampedModel):
    # Multi-Tenant: ربط المشروع بالشركة (Tenant)
    tenant = models.ForeignKey(
        'authentication.Tenant',
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,
        blank=True,
        db_index=True,
        help_text="الشركة التي ينتمي إليها المشروع"
    )
    PROJECT_TYPE_CHOICES = [
        ('villa', 'Villa'),
        ('commercial', 'Commercial'),
        ('maintenance', 'Maintenance'),
        ('governmental', 'Governmental'),
        ('fitout', 'Fit-out / Renovation'),
    ]
    VILLA_CATEGORY_CHOICES = [
        ('residential', 'Residential Villa'),
        ('commercial', 'Commercial Villa'),
    ]
    CONTRACT_TYPE_CHOICES = [
        ('new', 'New Contract'),
        ('continue', 'Continuation Contract'),
    ]

    # ↓↓↓ السماح بإنشاء مشروع بدون اسم
    name = models.CharField(max_length=200, blank=True, default="")
    project_type = models.CharField(max_length=40, choices=PROJECT_TYPE_CHOICES, blank=True)
    villa_category = models.CharField(max_length=40, choices=VILLA_CATEGORY_CHOICES, blank=True)
    contract_type = models.CharField(max_length=40, choices=CONTRACT_TYPE_CHOICES, blank=True)

    status = models.CharField(
        max_length=30,
        choices=[
            ('not_started', 'Not Yet Started'),  # 0
            ('execution_started', 'Execution Started'),  # 1
            ('under_execution', 'Under Execution'),  # 2
            ('temporarily_suspended', 'Temporarily Suspended'),  # 3
            ('handover_stage', 'In Handover Stage'),  # 4
            ('pending_financial_closure', 'Pending Financial Closure'),  # 5
            ('completed', 'Completed'),  # 6
            # الحالات القديمة (للتوافق)
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
        ],
        default='not_started',
    )

    # الكود الداخلي للمشروع — يبدأ بـ M ثم أرقام، مع شرط أن يكون آخر رقم فردياً
    internal_code = models.CharField(
        max_length=40,
        blank=True,
        db_index=True,
        validators=[RegexValidator(
            # M ثم أرقام، وآخر رقم فردي (يسمح بوجود أرقام زوجية في المنتصف)
            regex=r"^M[0-9]*[13579]$",
            message="Internal code must start with 'M' and end with an odd digit (1,3,5,7,9)."
        )],
        help_text="Starts with M, digits allowed, last digit must be odd (1,3,5,7,9).",
    )
    
    # ====== Workflow Fields ======
    # المرحلة الحالية في Workflow
    current_stage = models.ForeignKey(
        'authentication.WorkflowStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projects',
        help_text="المرحلة الحالية للمشروع في Workflow"
    )
    
    # حالة الموافقة
    approval_status = models.CharField(
        max_length=30,
        choices=[
            ('draft', 'Draft'),
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('delete_requested', 'Delete Requested'),
            ('delete_approved', 'Delete Approved'),
        ],
        default='draft',
        help_text="حالة الموافقة على المشروع"
    )
    
    # من طلب الحذف
    delete_requested_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delete_requests',
        help_text="المستخدم الذي طلب حذف المشروع"
    )
    delete_requested_at = models.DateTimeField(null=True, blank=True)
    delete_reason = models.TextField(blank=True, help_text="سبب طلب الحذف")
    
    # من وافق على الحذف
    delete_approved_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delete_approvals',
        help_text="المستخدم الذي وافق على حذف المشروع"
    )
    delete_approved_at = models.DateTimeField(null=True, blank=True)
    
    # من وافق/رفض آخر مرة
    last_approved_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approvals',
        help_text="المستخدم الذي وافق/رفض آخر مرة"
    )
    last_approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True, help_text="ملاحظات الموافقة/الرفض")

    def __str__(self):
        return self.name or f"Project #{self.id}"

    def calculate_status_from_payments(self):
        """
        حساب حالة المشروع بناءً على الدفعات وفقاً للقواعد:
        0. لم يبدأ بعد: توقيع العقد فقط ولم تُسجل أي دفعة
        1. بدأ التنفيذ: عند تسجيل دفعة مقدمة فقط (Advance Payment)
        2. قيد التنفيذ: عند تسجيل الدفعة الأولى بعد الدفعة المقدمة
        3. متوقف مؤقتا: إذا مضى على آخر دفعة أكثر من 6 أشهر
        4. في مرحلة التسليم: إذا وصلت نسبة الإنجاز إلى 91% أو أكثر
        5. قيد الإغلاق المالي: إذا تبقى مبلغ أقل من 5% من إجمالي قيمة العقد
        6. تم الانتهاء: عند تنفيذ التسوية المالية النهائية واكتمال نسبة الإنجاز إلى 100%
        """
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        
        # الحصول على العقد
        contract = None
        total_contract_value = Decimal('0')
        try:
            # ✅ استخدام getattr لتجنب DoesNotExist exception
            if hasattr(self, '_contract_cache'):
                contract = self._contract_cache
            elif hasattr(self, 'contract'):
                try:
                    contract = self.contract
                    self._contract_cache = contract
                    total_contract_value = contract.total_project_value or Decimal('0')
                except Exception:
                    contract = None
        except Exception:
            pass
        
        # الحصول على جميع الدفعات مرتبة حسب التاريخ
        try:
            payments = self.payments.all().order_by('date', 'created_at')
            payments_count = payments.count()
        except Exception:
            # ✅ في حالة عدم وجود جدول الدفعات أو خطأ، نرجع الحالة الافتراضية
            return 'not_started'
        
        # 0. لم يبدأ بعد: توقيع العقد فقط ولم تُسجل أي دفعة
        if payments_count == 0:
            # إذا كان هناك عقد موقّع، الحالة "لم يبدأ بعد"
            if contract and contract.contract_date:
                return 'not_started'
            # إذا لم يكن هناك عقد، نرجع الحالة الافتراضية
            return 'not_started'
        
        # الحصول على آخر دفعة
        last_payment = payments.last()
        total_paid = sum(Decimal(str(p.amount)) for p in payments)
        
        # حساب نسبة الإنجاز
        completion_percentage = 0
        if total_contract_value > 0:
            completion_percentage = float((total_paid / total_contract_value) * 100)
        
        # 6. تم الانتهاء: 100% إنجاز
        if completion_percentage >= 100:
            return 'completed'
        
        # 4. في مرحلة التسليم: 91% أو أكثر (لكن أقل من 100%)
        if completion_percentage >= 91:
            return 'handover_stage'
        
        # 5. قيد الإغلاق المالي: تبقى أقل من 5% (لكن لم يصل 91% بعد)
        if total_contract_value > 0:
            remaining = total_contract_value - total_paid
            remaining_percentage = float((remaining / total_contract_value) * 100)
            if remaining_percentage < 5 and completion_percentage < 91:
                return 'pending_financial_closure'
        
        # 3. متوقف مؤقتا: آخر دفعة قبل أكثر من 6 أشهر (لكن لم يصل 91% بعد)
        if last_payment:
            six_months_ago = timezone.now().date() - timedelta(days=180)
            if last_payment.date < six_months_ago and completion_percentage < 91:
                return 'temporarily_suspended'
        
        # 1. بدأ التنفيذ: دفعة مقدمة فقط
        if payments_count == 1:
            # التحقق من أن الدفعة هي دفعة مقدمة (من الوصف)
            payment_desc = (last_payment.description or "").lower()
            if 'advance' in payment_desc or 'مقدمة' in payment_desc or 'مقدم' in payment_desc:
                return 'execution_started'
            # إذا لم تكن دفعة مقدمة صريحة، نعتبرها بداية التنفيذ
            return 'execution_started'
        
        # 2. قيد التنفيذ: أكثر من دفعة واحدة (ولم تصل للحالات الأخرى)
        if payments_count > 1:
            return 'under_execution'
        
        # افتراضي
        return 'not_started'

    def update_status_from_payments(self):
        """تحديث حالة المشروع بناءً على الدفعات"""
        try:
            new_status = self.calculate_status_from_payments()
            if self.status != new_status:
                # ✅ استخدام update لتجنب إطلاق signals مرة أخرى
                Project.objects.filter(pk=self.pk).update(status=new_status)
                # ✅ تحديث instance المحلي
                self.status = new_status
                return True
        except Exception as e:
            # ✅ في حالة أي خطأ، نكمل بدون تحديث الحالة
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating project status from payments: {e}", exc_info=True)
        return False

    # Properties للـ serializer
    @property
    def has_siteplan(self):
        """تحقق من وجود SitePlan للمشروع"""
        # ✅ التحقق من وجود related object
        if not hasattr(self, '_state') or self._state.adding or not self.pk:
            # ✅ إذا كان المشروع جديداً (لم يُحفظ بعد)، نرجع False
            return False
        # ✅ استخدام query مباشر لتجنب DoesNotExist exception
        return SitePlan.objects.filter(project_id=self.pk).exists()

    @property
    def has_license(self):
        """تحقق من وجود BuildingLicense للمشروع"""
        # ✅ التحقق من وجود related object
        if not hasattr(self, '_state') or self._state.adding or not self.pk:
            # ✅ إذا كان المشروع جديداً (لم يُحفظ بعد)، نرجع False
            return False
        # ✅ استخدام query مباشر لتجنب DoesNotExist exception
        return BuildingLicense.objects.filter(project_id=self.pk).exists()

    @property
    def completion(self):
        """نسبة إكمال المشروع بناءً على الخطوات المكتملة"""
        if not hasattr(self, '_state') or self._state.adding or not self.pk:
            return 0
        completed = 0
        if self.has_siteplan:
            completed += 1
        if self.has_license:
            completed += 1
        if Contract.objects.filter(project_id=self.pk).exists():
            completed += 1
        return int((completed / 3) * 100) if completed > 0 else 0


# ====== مخطط الأرض ======
class SitePlan(TimeStampedModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="siteplan")

    municipality = models.CharField(max_length=120, blank=True)
    zone = models.CharField(max_length=120, blank=True)
    sector = models.CharField(max_length=120, blank=True)
    road_name = models.CharField(max_length=120, blank=True)
    plot_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    plot_area_sqft = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    land_no = models.CharField(max_length=120, blank=True)
    plot_address = models.CharField(max_length=255, blank=True)
    construction_status = models.CharField(max_length=120, blank=True)
    allocation_type = models.CharField(max_length=120, blank=True)
    land_use = models.CharField(max_length=120, blank=True)
    base_district = models.CharField(max_length=120, blank=True)
    overlay_district = models.CharField(max_length=120, blank=True)
    allocation_date = models.DateField(null=True, blank=True)

    # Developer info (for investment)
    developer_name = models.CharField(max_length=200, blank=True)
    project_no = models.CharField(max_length=120, blank=True)
    project_name = models.CharField(max_length=200, blank=True)

    # مصدر المشروع
    source_of_project = models.TextField(blank=True, help_text="مصدر المشروع")

    # Notes
    notes = models.TextField(blank=True)

    # Application / transaction info
    application_number = models.CharField(max_length=120, blank=True)
    application_date = models.DateField(null=True, blank=True)
    
    def get_application_file_path(instance, filename):
        """حفظ ملف مخطط الأرض باسم ثابت داخل مجلد المشروع لتفادي إضافة لاحقة."""
        ext = filename.split('.')[-1] if '.' in filename else 'pdf'
        project_part = instance.project_id or "project"
        return f"siteplans/applications/{project_part}/مخطط_الأرض.{ext}"
    
    application_file = models.FileField(upload_to=get_application_file_path, null=True, blank=True)

    def __str__(self):
        return f"SitePlan #{self.id} for {self.project.name or self.project_id}"


class SitePlanOwner(TimeStampedModel):
    siteplan = models.ForeignKey(SitePlan, on_delete=models.CASCADE, related_name="owners")
    owner_name_ar = models.CharField(max_length=200, blank=True)
    owner_name_en = models.CharField(max_length=200, blank=True)
    nationality = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    id_issue_date = models.DateField(null=True, blank=True)
    id_expiry_date = models.DateField(null=True, blank=True)
    
    def get_id_attachment_path(instance, filename):
        """حفظ ملف بطاقة الهوية باسم ثابت داخل مجلد المالك/المشروع لتفادي إضافة لاحقة."""
        ext = filename.split('.')[-1] if '.' in filename else 'pdf'
        owner_index = getattr(instance, '_owner_index', instance.id if instance.id else 1)
        siteplan_part = instance.siteplan_id or "siteplan"
        return f"owners/ids/{siteplan_part}/بطاقة_الهوية_{owner_index}.{ext}"
    
    id_attachment = models.FileField(upload_to=get_id_attachment_path, null=True, blank=True)
    right_hold_type = models.CharField(max_length=120, blank=True, default="Ownership")
    share_possession = models.CharField(max_length=120, blank=True)
    share_percent = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))], default=100
    )
    # ✅ حقل العمر المحسوب (يتم حفظه تلقائياً عند الحفظ)
    age = models.PositiveIntegerField(null=True, blank=True, editable=False, help_text="العمر محسوب تلقائياً من رقم الهوية")
    # ✅ المالك المفوض (يتم اختياره صراحة من الواجهة)
    is_authorized = models.BooleanField(default=False, help_text="المالك المفوض (يتم اختياره صراحة)")

    def calculate_age_from_id(self):
        """حساب العمر من رقم الهوية الإماراتية"""
        if not self.id_number:
            return None
        
        import re
        from datetime import date
        
        # إزالة الفواصل والمسافات
        cleaned = re.sub(r'[-\s]', '', str(self.id_number))
        
        # محاولة استخراج سنة الميلاد من التنسيق: 784-YYYY-XXXXXXX-X
        birth_year = None
        
        # طريقة 1: إذا كان الرقم يحتوي على فواصل
        if '-' in str(self.id_number):
            parts = str(self.id_number).split('-')
            if len(parts) >= 2 and parts[1]:
                try:
                    year = int(parts[1].strip())
                    if 1900 <= year <= date.today().year:
                        birth_year = year
                except (ValueError, TypeError):
                    pass
        
        # طريقة 2: إذا لم نجد سنة من الفواصل، نحاول من المواضع 4-7
        if birth_year is None and len(cleaned) >= 8:
            try:
                year = int(cleaned[3:7])
                if 1900 <= year <= date.today().year:
                    birth_year = year
            except (ValueError, TypeError):
                pass
        
        # حساب العمر
        if birth_year:
            current_year = date.today().year
            age = current_year - birth_year
            return age if age >= 0 else None
        
        return None

    def save(self, *args, **kwargs):
        """حساب العمر تلقائياً قبل الحفظ"""
        self.age = self.calculate_age_from_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.owner_name_ar or self.owner_name_en or "Unnamed Owner"


# ====== الاستشاري ======
class Consultant(TimeStampedModel):
    """نموذج الاستشاري - كيان مستقل مع بيانات موحدة"""
    name = models.CharField(max_length=200, help_text="اسم الاستشاري (عربي)")
    name_en = models.CharField(max_length=200, blank=True, help_text="اسم الاستشاري (إنجليزي)")
    license_no = models.CharField(max_length=120, blank=True, help_text="رقم رخصة الاستشاري")
    
    # صورة الاستشاري
    def get_consultant_image_path(instance, filename):
        """حفظ صورة الاستشاري"""
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        consultant_id = instance.id or "new"
        return f"consultants/{consultant_id}/image.{ext}"
    
    image = models.ImageField(
        upload_to=get_consultant_image_path,
        null=True,
        blank=True,
        help_text="صورة الاستشاري"
    )
    
    # بيانات إضافية
    phone = models.CharField(max_length=20, blank=True, help_text="رقم الهاتف")
    email = models.EmailField(blank=True, help_text="البريد الإلكتروني")
    address = models.TextField(blank=True, help_text="العنوان")
    notes = models.TextField(blank=True, help_text="ملاحظات")
    
    class Meta:
        verbose_name = "استشاري"
        verbose_name_plural = "استشاريون"
        # منع تكرار الاستشاريين بنفس الاسم في نفس الشركة (إذا لم يكن هناك رخصة)
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['tenant', 'license_no']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.license_no or 'No License'})"


# ====== ربط الاستشاري بالمشاريع ======
class ProjectConsultant(TimeStampedModel):
    """ربط الاستشاري بالمشروع مع تحديد الدور (تصميم/إشراف)"""
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='consultants',
        help_text="المشروع"
    )
    consultant = models.ForeignKey(
        Consultant,
        on_delete=models.CASCADE,
        related_name='projects',
        help_text="الاستشاري"
    )
    ROLE_CHOICES = [
        ('design', 'استشاري التصميم'),
        ('supervision', 'استشاري الإشراف'),
    ]
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="دور الاستشاري في المشروع"
    )
    
    class Meta:
        verbose_name = "استشاري المشروع"
        verbose_name_plural = "استشاريو المشاريع"
        # منع تكرار نفس الاستشاري بنفس الدور في نفس المشروع
        unique_together = [['project', 'consultant', 'role']]
        ordering = ['project', 'role']
        indexes = [
            models.Index(fields=['project', 'role']),
            models.Index(fields=['consultant', 'role']),
        ]
    
    def __str__(self):
        role_display = dict(self.ROLE_CHOICES).get(self.role, self.role)
        return f"{self.consultant.name} - {role_display} ({self.project.name or self.project.id})"


# ====== ترخيص البناء ======
class BuildingLicense(TimeStampedModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="license")

    # General license data
    license_type = models.CharField(max_length=120, blank=True)

    # (المطور) سنابشوت من الـ SitePlan
    project_no = models.CharField(max_length=120, blank=True)
    project_name = models.CharField(max_length=200, blank=True)

    # (الرخصة) الحقلان الجديدان
    license_project_no = models.CharField(max_length=120, blank=True)
    license_project_name = models.CharField(max_length=200, blank=True)

    license_no = models.CharField(max_length=120, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    last_issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    technical_decision_ref = models.CharField(max_length=120, blank=True)
    technical_decision_date = models.DateField(null=True, blank=True)
    license_notes = models.TextField(blank=True)
    
    def get_building_license_file_path(instance, filename):
        """حفظ ملف رخصة البناء باسم ثابت داخل مجلد المشروع لتفادي إضافة لاحقة."""
        ext = filename.split('.')[-1] if '.' in filename else 'pdf'
        project_part = instance.project_id or "project"
        return f"licenses/{project_part}/رخصة_البناء.{ext}"
    
    building_license_file = models.FileField(upload_to=get_building_license_file_path, null=True, blank=True)

    # Plot / land data
    city = models.CharField(max_length=120, blank=True)
    zone = models.CharField(max_length=120, blank=True)
    sector = models.CharField(max_length=120, blank=True)
    plot_no = models.CharField(max_length=120, blank=True)
    plot_address = models.CharField(max_length=255, blank=True)
    plot_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    land_use = models.CharField(max_length=120, blank=True)
    land_use_sub = models.CharField(max_length=120, blank=True)
    land_plan_no = models.CharField(max_length=120, blank=True)

    # Parties
    # ===== استشاري التصميم / الإشراف =====
    consultant_same = models.BooleanField(default=True)

    # ✅ الاستشاريون الجدد (موصى به)
    design_consultant = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='design_licenses',
        help_text="استشاري التصميم"
    )
    supervision_consultant = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervision_licenses',
        help_text="استشاري الإشراف"
    )

    # ⚠️ الحقول القديمة (للتوافق مع البيانات الموجودة - سيتم إهمالها تدريجياً)
    design_consultant_name = models.CharField(max_length=200, blank=True)
    design_consultant_name_en = models.CharField(max_length=200, blank=True)
    design_consultant_license_no = models.CharField(max_length=120, blank=True)

    supervision_consultant_name = models.CharField(max_length=200, blank=True)
    supervision_consultant_name_en = models.CharField(max_length=200, blank=True)
    supervision_consultant_license_no = models.CharField(max_length=120, blank=True)
    
    def get_design_consultant_name(self):
        """الحصول على اسم استشاري التصميم (من Consultant أو الحقل القديم)"""
        if self.design_consultant:
            return self.design_consultant.name
        return self.design_consultant_name or ""
    
    def get_design_consultant_name_en(self):
        """الحصول على الاسم الإنجليزي لاستشاري التصميم"""
        if self.design_consultant:
            return self.design_consultant.name_en or ""
        return self.design_consultant_name_en or ""
    
    def get_supervision_consultant_name(self):
        """الحصول على اسم استشاري الإشراف"""
        if self.supervision_consultant:
            return self.supervision_consultant.name
        return self.supervision_consultant_name or ""
    
    def get_supervision_consultant_name_en(self):
        """الحصول على الاسم الإنجليزي لاستشاري الإشراف"""
        if self.supervision_consultant:
            return self.supervision_consultant.name_en or ""
        return self.supervision_consultant_name_en or ""

    contractor_name = models.CharField(max_length=200, blank=True)
    contractor_name_en = models.CharField(max_length=200, blank=True)
    contractor_license_no = models.CharField(max_length=120, blank=True)
    contractor_phone = models.CharField(max_length=20, blank=True)
    contractor_email = models.EmailField(blank=True)

    # Owners snapshot داخل الرخصة
    owners = models.JSONField(default=list, blank=True)

    # Read-only snapshot من SitePlan
    siteplan_snapshot = models.JSONField(default=dict, editable=False)

    def __str__(self):
        return f"Building License {self.license_no or self.id}"


# ====== العقد ======
class Contract(TimeStampedModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="contract")

    contract_classification = models.CharField(max_length=120, blank=True)
    contract_type = models.CharField(max_length=120, blank=True)
    tender_no = models.CharField(max_length=120, blank=True)
    contract_date = models.DateField(null=True, blank=True)
    contractor_name = models.CharField(max_length=200, blank=True)
    contractor_name_en = models.CharField(max_length=200, blank=True)
    contractor_trade_license = models.CharField(max_length=120, blank=True)
    contractor_phone = models.CharField(max_length=20, blank=True)
    contractor_email = models.EmailField(blank=True)

    total_project_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_bank_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_owner_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    project_duration_months = models.PositiveIntegerField(default=0)

    start_order_date = models.DateField(null=True, blank=True)
    project_end_date = models.DateField(null=True, blank=True)
    start_order_notes = models.TextField(blank=True, help_text="ملاحظات أمر المباشرة")

    # Owner consultant fees
    owner_includes_consultant = models.BooleanField(default=False)
    owner_fee_design_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    owner_fee_supervision_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    owner_fee_extra_mode = models.CharField(max_length=40, blank=True)
    owner_fee_extra_value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    # Bank consultant fees
    bank_includes_consultant = models.BooleanField(default=False)
    bank_fee_design_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bank_fee_supervision_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bank_fee_extra_mode = models.CharField(max_length=40, blank=True)
    bank_fee_extra_value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    # Snapshot
    license_snapshot = models.JSONField(default=dict, editable=False)
    
    # بيانات الملاك (قابلة للتحرير في العقد)
    owners = models.JSONField(
        default=list, 
        blank=True, 
        help_text="بيانات الملاك في العقد (قابلة للتحرير): [{'owner_name_ar': '...', 'owner_name_en': '...', 'phone': '...', 'email': '...', ...}, ...]"
    )
    
    # الملاحظات العامة
    general_notes = models.TextField(blank=True, help_text="ملاحظات عامة")

    # المرفقات الديناميكية
    attachments = models.JSONField(default=list, blank=True, help_text="مرفقات العقد الديناميكية")
    
    # التمديدات
    extensions = models.JSONField(
        default=list, 
        blank=True, 
        help_text="قائمة التمديدات: [{'reason': 'string', 'days': int, 'months': int, 'extension_date': 'string', 'approval_number': 'string', 'file_url': 'string', 'file_name': 'string'}, ...]"
    )
    
    # الملفات القديمة (للتوافق مع البيانات الموجودة)
    contract_file = models.FileField(upload_to="contracts/main/", null=True, blank=True)
    contract_appendix_file = models.FileField(upload_to="contracts/appendix/", null=True, blank=True)
    contract_explanation_file = models.FileField(upload_to="contracts/explanations/", null=True, blank=True)
    start_order_file = models.FileField(upload_to="contracts/start_orders/", null=True, blank=True)
    
    # ✅ المرفقات الثابتة
    quantities_table_file = models.FileField(upload_to="contracts/quantities/", null=True, blank=True, help_text="جدول الكميات")
    approved_materials_table_file = models.FileField(upload_to="contracts/materials/", null=True, blank=True, help_text="جدول المواد المعتمدة")
    price_offer_file = models.FileField(upload_to="contracts/price_offer/", null=True, blank=True, help_text="عرض السعر")
    contractual_drawings_file = models.FileField(upload_to="contracts/drawings/", null=True, blank=True, help_text="مخططات تعاقدية")
    general_specifications_file = models.FileField(upload_to="contracts/specifications/", null=True, blank=True, help_text="المواصفات العامة والخاصة")

    def __str__(self):
        return f"Contract for {self.project.name or self.project_id}"



# ====== أمر الترسية ======
class Awarding(TimeStampedModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="awarding")

    # تاريخ أمر الترسية
    award_date = models.DateField(null=True, blank=True)
    
    # رقم تسجيل الاستشاري (VR-xxxx)
    consultant_registration_number = models.CharField(max_length=120, blank=True)
    
    # رقم المشروع
    project_number = models.CharField(max_length=120, blank=True)
    
    # رقم تسجيل المقاول (VR-xxxx)
    contractor_registration_number = models.CharField(max_length=120, blank=True)
    
    # ملف أمر الترسية
    awarding_file = models.FileField(upload_to="awarding/", null=True, blank=True)

    def __str__(self):
        return f"Awarding for {self.project.name or self.project_id}"


# ====== أوامر التغيير السعري (Price Change Orders) ======
class Variation(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="variations")
    variation_number = models.CharField(max_length=100, blank=True, unique=True, help_text="رقم التعديل")
    description = models.TextField(blank=True, help_text="الوصف")
    final_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="المبلغ الفعلي")
    consultant_fees_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))], help_text="نسبة أتعاب الاستشاري (%) من المبلغ الفعلي")
    consultant_fees = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="أتعاب الاستشاري (محسوبة تلقائياً من النسبة)")
    contractor_engineer_fees = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="مهندس المقاول (Head and Profit) (مبلغ ثابت)")
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="المبلغ الإجمالي")
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="الخصم")
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="المبلغ الصافي")
    vat = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="الضريبة")
    net_amount_with_vat = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], help_text="المبلغ الصافي بالضريبة")
    variation_invoice_file = models.FileField(upload_to='variations/invoices/', blank=True, null=True, help_text="فاتورة التعديل")
    # Legacy fields (kept for backward compatibility)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], help_text="المبلغ (legacy - use final_amount)")
    approval_date = models.DateField(null=True, blank=True)
    approved_by = models.CharField(max_length=200, blank=True)
    attachments = models.JSONField(default=list, blank=True, help_text="List of attachment file paths/URLs")

    class Meta:
        db_table = 'projects_variation'
        verbose_name = 'Price Change Order'
        verbose_name_plural = 'Price Change Orders'
        ordering = ['-approval_date', '-created_at']

    def __str__(self):
        return f"Variation {self.variation_number or self.id} - {self.final_amount} for {self.project.name or self.project_id}"


# ====== الفواتير ======
class ActualInvoice(TimeStampedModel):
    """Invoice - linked to payment"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="actual_invoices")
    payment = models.OneToOneField('Payment', on_delete=models.CASCADE, related_name="actual_invoice", null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    invoice_date = models.DateField()
    invoice_number = models.CharField(max_length=100, blank=True, unique=True, null=True)
    description = models.TextField(blank=True)
    items = models.JSONField(default=list, blank=True, help_text="Invoice items: [{description, quantity, unit_price, total}]")

    class Meta:
        db_table = 'projects_actual_invoice'
        verbose_name = 'Actual Invoice'
        verbose_name_plural = 'Actual Invoices'
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return f"Actual Invoice {self.invoice_number or self.id} - {self.amount}"


# ====== الدفعات ======
class Payment(TimeStampedModel):
    PAYER_CHOICES = [
        ('bank', 'Bank'),
        ('owner', 'Owner'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash_deposit', 'Cash Deposit in Company Bank Account'),
        ('cash_office', 'Cash Payment in Office'),
        ('bank_transfer', 'Bank Transfer'),
        ('bank_cheque', 'Bank Cheque'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    payer = models.CharField(max_length=20, choices=PAYER_CHOICES, default='owner')
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    # Bank transfer details
    recipient_account_number = models.CharField(max_length=100, blank=True, help_text="رقم الحساب المستلم")
    sender_account_number = models.CharField(max_length=100, blank=True, help_text="رقم الحساب الراسل (للتحويل البنكي)")
    transferor_name = models.CharField(max_length=200, blank=True, help_text="اسم المحول (للتحويل البنكي) / اسم الراسل (للإيداع النقدي)")
    # Bank cheque details
    cheque_holder_name = models.CharField(max_length=200, blank=True, help_text="اسم صاحب الشيك")
    cheque_account_number = models.CharField(max_length=100, blank=True, help_text="رقم الحساب الذي سيخضع فيه الشيك")
    cheque_date = models.DateField(null=True, blank=True, help_text="تاريخ الشيك")
    # Bank payment specific fields
    project_financial_account = models.CharField(max_length=100, blank=True, help_text="رقم الحساب المالي للمشروع (يبدأ بـ PRJ)")
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="نسبة الإنجاز")
    bank_payment_attachments = models.FileField(upload_to='payments/bank_attachments/', blank=True, null=True, help_text="مرفقات دفعة البنك")
    # File attachments
    deposit_slip = models.FileField(upload_to='payments/deposit_slips/', blank=True, null=True, help_text="Deposit Slip / Bank Deposit Proof")
    invoice_file = models.FileField(upload_to='payments/invoices/', blank=True, null=True, help_text="Invoice Used for Payment (فاتورة الدفع)")
    receipt_voucher = models.FileField(upload_to='payments/receipts/', blank=True, null=True, help_text="Receipt Voucher (سند قبض)")
    # Note: actual_invoice is accessed via reverse relationship: payment.actual_invoice

    class Meta:
        db_table = 'projects_payment'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-date', '-created_at']

    def __str__(self):
        payer_name = dict(self.PAYER_CHOICES).get(self.payer, self.payer)
        if self.project:
            return f"{payer_name} Payment {self.amount} for {self.project.name or self.project_id} on {self.date}"
        return f"{payer_name} Payment {self.amount} on {self.date}"

    def clean(self):
        """Validate payment method based on payer"""
        from django.core.exceptions import ValidationError
        
        if self.payer == 'bank':
            if self.payment_method != 'bank_transfer':
                raise ValidationError({
                    'payment_method': 'Bank payments must use Bank Transfer only.'
                })
        elif self.payer == 'owner':
            if not self.payment_method:
                raise ValidationError({
                    'payment_method': 'Payment method is required for owner payments.'
                })
            if self.payment_method not in ['cash_deposit', 'cash_office', 'bank_transfer', 'bank_cheque']:
                raise ValidationError({
                    'payment_method': 'Invalid payment method for owner payments.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
