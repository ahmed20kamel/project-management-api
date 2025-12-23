from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid


# ====== Tenant Model ======
class Tenant(models.Model):
    """نموذج الشركة (Tenant) في نظام Multi-Tenant"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True, help_text="اسم الشركة")
    slug = models.SlugField(max_length=200, unique=True, db_index=True, help_text="معرف فريد للشركة (URL-friendly)")
    
    # Status
    is_active = models.BooleanField(default=True, help_text="هل الشركة نشطة؟")
    is_trial = models.BooleanField(default=True, help_text="هل الشركة في فترة تجريبية؟")
    trial_ends_at = models.DateTimeField(null=True, blank=True, help_text="تاريخ انتهاء الفترة التجريبية")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_tenant'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # ✅ فقط إذا لم يكن slug موجوداً، نولده تلقائياً
        # ✅ إذا كان slug موجوداً (تم إدخاله يدوياً)، نستخدمه كما هو
        if not self.slug:
            # إنشاء slug من الاسم
            from django.utils.text import slugify
            import re
            import unicodedata
            
            # تحويل النص العربي إلى slug
            # استخدام transliteration بسيط للنصوص العربية
            text = self.name
            
            # محاولة استخدام unidecode إذا كان متاحاً
            try:
                from unidecode import unidecode
                text = unidecode(text)
            except ImportError:
                # إذا لم يكن unidecode متاحاً، استخدم طريقة بسيطة
                # تحويل الأحرف العربية الشائعة
                arabic_to_latin = {
                    'أ': 'a', 'إ': 'i', 'آ': 'a', 'ا': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th',
                    'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z',
                    'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
                    'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
                    'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'h', 'ئ': 'y', 'ء': 'a',
                }
                for arabic, latin in arabic_to_latin.items():
                    text = text.replace(arabic, latin)
            
            # إزالة الأحرف الخاصة والمسافات المتعددة
            text = re.sub(r'[^\w\s-]', '', text)
            text = re.sub(r'[-\s]+', '-', text)
            
            # استخدام slugify
            self.slug = slugify(text)
            
            # إذا كان slug فارغاً بعد التحويل، استخدم اسم إنجليزي بديل
            if not self.slug:
                # استخدام أول حرف من كل كلمة
                words = self.name.split()
                if words:
                    self.slug = '-'.join([w[0].lower() if w else 'x' for w in words[:3]])
                else:
                    self.slug = 'company'
            
            # التأكد من أن الـ slug فريد
            original_slug = self.slug
            counter = 1
            while Tenant.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        else:
            # ✅ إذا كان slug موجوداً، نتحقق فقط من أنه فريد
            original_slug = self.slug
            counter = 1
            while Tenant.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


# ====== Tenant Settings Model ======
class TenantSettings(models.Model):
    """إعدادات الشركة (Tenant Settings)"""
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='settings',
        primary_key=True
    )
    
    # Company Information
    company_name = models.CharField(max_length=200, help_text="اسم الشركة")
    company_logo = models.ImageField(
        upload_to='tenants/logos/',
        null=True,
        blank=True,
        help_text="شعار الشركة"
    )
    company_license_number = models.CharField(max_length=100, blank=True, help_text="رقم الرخصة")
    company_email = models.EmailField(help_text="البريد الإلكتروني للشركة")
    company_phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="رقم الهاتف"
    )
    company_address = models.TextField(blank=True, help_text="عنوان الشركة")
    company_country = models.CharField(max_length=100, blank=True, help_text="الدولة")
    company_city = models.CharField(max_length=100, blank=True, help_text="المدينة")
    company_description = models.TextField(blank=True, help_text="وصف الشركة")
    company_activity_type = models.CharField(
        max_length=50,
        choices=[
            ('construction', 'مقاولات'),
            ('project_management', 'إدارة مشاريع'),
            ('engineering', 'مكتب هندسي'),
            ('consulting', 'استشارات'),
        ],
        default='construction',
        help_text="نوع النشاط"
    )
    
    # ====== بيانات المقاول (Contractor Info) ======
    # المقاول = الشركة نفسها (Company = Contractor)
    # هذه البيانات ثابتة وتُستخدم تلقائياً في جميع المشاريع والعقود
    contractor_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="اسم المقاول (عربي) - نفس اسم الشركة عادة"
    )
    contractor_name_en = models.CharField(
        max_length=200,
        blank=True,
        help_text="اسم المقاول (إنجليزي)"
    )
    contractor_license_no = models.CharField(
        max_length=120,
        blank=True,
        help_text="رقم رخصة المقاول"
    )
    contractor_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="رقم هاتف المقاول"
    )
    contractor_email = models.EmailField(
        blank=True,
        help_text="البريد الإلكتروني للمقاول"
    )
    contractor_address = models.TextField(
        blank=True,
        help_text="عنوان المقاول"
    )
    
    # Additional Settings (يمكن إضافة المزيد لاحقاً)
    currency = models.CharField(max_length=10, default='SAR', help_text="العملة")
    timezone = models.CharField(max_length=50, default='Asia/Riyadh', help_text="المنطقة الزمنية")
    language = models.CharField(max_length=10, default='ar', choices=[('ar', 'Arabic'), ('en', 'English')])
    
    # Theme/Branding Settings
    primary_color = models.CharField(
        max_length=7,
        default='#f97316',
        help_text="اللون الأساسي للشركة (Hex Color)",
        validators=[RegexValidator(
            regex=r'^#[0-9A-Fa-f]{6}$',
            message="Primary color must be a valid hex color (e.g., #f97316)"
        )]
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#ea580c',
        help_text="اللون الثانوي للشركة (Hex Color)",
        validators=[RegexValidator(
            regex=r'^#[0-9A-Fa-f]{6}$',
            message="Secondary color must be a valid hex color (e.g., #ea580c)"
        )]
    )
    background_image = models.ImageField(
        upload_to='tenants/backgrounds/',
        null=True,
        blank=True,
        help_text="صورة خلفية صفحة تسجيل الدخول"
    )
    
    # Subscription & Limits Settings
    max_users = models.PositiveIntegerField(
        default=10,
        help_text="الحد الأقصى لعدد المستخدمين المسموح به"
    )
    max_projects = models.PositiveIntegerField(
        default=50,
        help_text="الحد الأقصى لعدد المشاريع المسموح به"
    )
    subscription_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="تاريخ بداية الاشتراك"
    )
    subscription_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="تاريخ نهاية الاشتراك"
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'نشط'),
            ('suspended', 'متوقف'),
            ('expired', 'منتهي'),
            ('trial', 'تجريبي'),
        ],
        default='trial',
        help_text="حالة الاشتراك"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_tenant_settings'
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"


# ====== User Manager ======
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# ====== User Model ======
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )]
    )
    
    # Profile Picture
    avatar = models.ImageField(
        upload_to='users/avatars/',
        null=True,
        blank=True,
        help_text="صورة المستخدم"
    )
    
    # Personal Health Information (اختياري)
    date_of_birth = models.DateField(null=True, blank=True, help_text="تاريخ الميلاد")
    blood_type = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ('A+', 'A+'),
            ('A-', 'A-'),
            ('B+', 'B+'),
            ('B-', 'B-'),
            ('AB+', 'AB+'),
            ('AB-', 'AB-'),
            ('O+', 'O+'),
            ('O-', 'O-'),
        ],
        help_text="فصيلة الدم"
    )
    emergency_contact_name = models.CharField(max_length=200, blank=True, help_text="اسم جهة الاتصال في حالات الطوارئ")
    emergency_contact_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="رقم جهة الاتصال في حالات الطوارئ"
    )
    medical_notes = models.TextField(blank=True, help_text="ملاحظات طبية (حساسية، أدوية، إلخ)")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    
    # Role
    role = models.ForeignKey('Role', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    
    # Multi-Tenant: ربط المستخدم بالشركة (Tenant)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        help_text="الشركة التي ينتمي إليها المستخدم"
    )
    
    # Onboarding Status
    onboarding_completed = models.BooleanField(
        default=False,
        help_text="هل أكمل المستخدم عملية الإعداد الأولي (Onboarding)?"
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    class Meta:
        db_table = 'authentication_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def has_permission(self, permission_code):
        """التحقق من وجود صلاحية معينة للمستخدم"""
        if self.is_superuser:
            return True
        
        if self.role:
            return self.role.permissions.filter(code=permission_code).exists()
        
        return False
    
    def get_all_permissions(self):
        """الحصول على جميع الصلاحيات للمستخدم"""
        if self.is_superuser:
            return Permission.objects.values_list('code', flat=True)
        
        if self.role:
            return self.role.permissions.values_list('code', flat=True)
        
        return []


# ====== Permission Model ======
class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True, db_index=True, help_text="مثال: project.create")
    name = models.CharField(max_length=200, help_text="اسم الصلاحية بالعربية")
    name_en = models.CharField(max_length=200, blank=True, help_text="اسم الصلاحية بالإنجليزية")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, help_text="مثال: project, files, user")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_permission'
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
        ordering = ['category', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


# ====== Role Model ======
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    name_en = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    permissions = models.ManyToManyField(Permission, related_name='roles', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_permission_codes(self):
        """الحصول على قائمة أكواد الصلاحيات"""
        return list(self.permissions.values_list('code', flat=True))


# ====== Workflow Stage Model ======
class WorkflowStage(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="مثال: stage_1, stage_2")
    name = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, help_text="ترتيب المرحلة")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_workflow_stage'
        verbose_name = 'Workflow Stage'
        verbose_name_plural = 'Workflow Stages'
        ordering = ['order', 'code']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


# ====== Workflow Rule Model ======
class WorkflowRule(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create / Enter Data'),
        ('edit', 'Edit'),
        ('submit', 'Submit'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('delete_request', 'Request Delete'),
        ('delete_approve', 'Approve Delete'),
    ]
    
    stage = models.ForeignKey(WorkflowStage, on_delete=models.CASCADE, related_name='rules')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    required_permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='workflow_rules',
        help_text="الصلاحية المطلوبة لتنفيذ هذا الإجراء في هذه المرحلة"
    )
    
    # Optional: يمكن تحديد Role محدد بدلاً من Permission
    allowed_roles = models.ManyToManyField(Role, related_name='workflow_rules', blank=True)
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_workflow_rule'
        verbose_name = 'Workflow Rule'
        verbose_name_plural = 'Workflow Rules'
        unique_together = [['stage', 'action']]
        ordering = ['stage__order', 'action']
    
    def __str__(self):
        return f"{self.stage.name} - {self.get_action_display()}"


# ====== Audit Log Model ======
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('edit', 'Edit'),
        ('delete', 'Delete'),
        ('submit', 'Submit'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('delete_request', 'Request Delete'),
        ('delete_approve', 'Approve Delete'),
        ('view', 'View'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    
    # Model info
    model_name = models.CharField(max_length=100, help_text="اسم الـ Model (مثال: Project, Contract)")
    object_id = models.CharField(max_length=255, null=True, blank=True, help_text="ID الكائن (يمكن أن يكون UUID أو رقم)")
    
    # Details
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True, help_text="التغييرات التي تمت (قبل/بعد)")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Workflow info
    stage = models.ForeignKey(WorkflowStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'authentication_audit_log'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email if self.user else 'Unknown'} - {self.get_action_display()} - {self.model_name}"


# ====== Pending Change Model ======
class PendingChange(models.Model):
    """نموذج لتخزين التعديلات المعلقة التي تحتاج موافقة من المدير"""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]
    
    # User and Tenant info
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pending_changes',
        help_text="المستخدم الذي طلب التعديل"
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='pending_changes',
        help_text="الشركة التي ينتمي إليها التعديل"
    )
    
    # Change details
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, help_text="نوع العملية")
    model_name = models.CharField(max_length=100, help_text="اسم النموذج (مثال: Project, SitePlan)")
    object_id = models.CharField(max_length=255, help_text="معرف الكائن (يمكن أن يكون UUID أو رقم)")
    
    # Data
    data = models.JSONField(default=dict, help_text="البيانات الجديدة (لإنشاء/تعديل)")
    old_data = models.JSONField(default=dict, blank=True, help_text="البيانات القديمة (للتعديل/الحذف)")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_changes',
        help_text="المدير الذي راجع التعديل"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, help_text="تاريخ المراجعة")
    review_notes = models.TextField(blank=True, help_text="ملاحظات المراجعة")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'authentication_pending_change'
        verbose_name = 'Pending Change'
        verbose_name_plural = 'Pending Changes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', '-created_at']),
            models.Index(fields=['requested_by', '-created_at']),
            models.Index(fields=['model_name', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} {self.model_name} - {self.status} by {self.requested_by.email if self.requested_by else 'Unknown'}"

