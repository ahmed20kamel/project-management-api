# backend/authentication/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Role, Permission, WorkflowStage, WorkflowRule, AuditLog, Tenant, TenantSettings, PendingChange


# ====== Tenant Serializer ======
class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'is_active', 'is_trial', 'trial_ends_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_slug(self, value):
        """التحقق من أن slug فريد وصالح - فقط السوبر أدمن يمكنه تعديل slug"""
        if value:
            # تنظيف slug (إزالة المسافات وتحويل إلى أحرف صغيرة)
            value = value.strip().lower()
            
            # التحقق من أن slug يحتوي فقط على أحرف صالحة (a-z, 0-9, -)
            import re
            if not re.match(r'^[a-z0-9-]+$', value):
                raise serializers.ValidationError('كود الشركة يجب أن يحتوي فقط على أحرف إنجليزية صغيرة وأرقام وشرطة')
            
            # التحقق من أن slug فريد (إذا كان التحديث)
            if self.instance:
                if Tenant.objects.filter(slug=value).exclude(pk=self.instance.pk).exists():
                    raise serializers.ValidationError('كود الشركة مستخدم بالفعل')
            else:
                if Tenant.objects.filter(slug=value).exists():
                    raise serializers.ValidationError('كود الشركة مستخدم بالفعل')
        return value


# ====== Tenant Settings Serializer ======
class TenantSettingsSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    logo_url = serializers.SerializerMethodField()
    background_image_url = serializers.SerializerMethodField()
    current_users_count = serializers.SerializerMethodField()
    current_projects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantSettings
        fields = [
            'tenant', 'company_name', 'company_logo', 'logo_url', 'background_image', 'background_image_url',
            'company_license_number', 'company_email', 'company_phone', 'company_address',
            'company_country', 'company_city', 'company_description', 'company_activity_type',
            'currency', 'timezone', 'language',
            'primary_color', 'secondary_color',
            # بيانات المقاول (Contractor Info)
            'contractor_name', 'contractor_name_en', 'contractor_license_no',
            'contractor_phone', 'contractor_email', 'contractor_address',
            'max_users', 'max_projects',
            'current_users_count', 'current_projects_count',
            'subscription_start_date', 'subscription_end_date', 'subscription_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'current_users_count', 'current_projects_count', 'logo_url', 'background_image_url']
    
    def update(self, instance, validated_data):
        """تحديث البيانات مع التأكد من حفظ جميع الحقول"""
        import logging
        logger = logging.getLogger(__name__)
        
        # ✅ Logging قبل التحديث
        logger.info(f"Updating TenantSettings for tenant {instance.tenant.id}")
        logger.info(f"Validated data: {validated_data}")
        
        # ✅ تحديث جميع الحقول
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # ✅ حفظ في قاعدة البيانات
        instance.save()
        
        # ✅ Logging بعد التحديث
        logger.info(f"TenantSettings updated successfully")
        logger.info(f"Company Logo after save: {instance.company_logo}")
        logger.info(f"Primary Color after save: {instance.primary_color}")
        logger.info(f"Secondary Color after save: {instance.secondary_color}")
        
        return instance
    
    def get_logo_url(self, obj):
        if obj.company_logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.company_logo.url)
            return obj.company_logo.url
        return None
    
    def get_background_image_url(self, obj):
        if obj.background_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.background_image.url)
            return obj.background_image.url
        return None
    
    def get_current_users_count(self, obj):
        """عدد المستخدمين الحاليين في الشركة"""
        return User.objects.filter(tenant=obj.tenant, is_active=True).count()
    
    def get_current_projects_count(self, obj):
        """عدد المشاريع الحالية في الشركة"""
        from projects.models import Project
        return Project.objects.filter(tenant=obj.tenant).count()


# ====== Tenant Theme Serializer (للقراءة فقط) ======
class TenantThemeSerializer(serializers.ModelSerializer):
    """Serializer مبسط لقراءة Theme الشركة فقط"""
    logo_url = serializers.SerializerMethodField()
    background_image_url = serializers.SerializerMethodField()
    tenant_id = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantSettings
        fields = [
            'tenant_id', 'company_name', 'logo_url', 'background_image_url',
            'primary_color', 'secondary_color',
        ]
        read_only_fields = fields
    
    def get_tenant_id(self, obj):
        """الحصول على tenant_id"""
        try:
            return str(obj.tenant.id) if obj.tenant else None
        except Exception:
            return None
    
    def get_logo_url(self, obj):
        try:
            if obj.company_logo:
                request = self.context.get('request')
                if request:
                    try:
                        return request.build_absolute_uri(obj.company_logo.url)
                    except Exception:
                        # إذا فشل بناء URL، نرجع المسار النسبي
                        return obj.company_logo.url if hasattr(obj.company_logo, 'url') else None
                return obj.company_logo.url if hasattr(obj.company_logo, 'url') else None
        except Exception:
            return None
        return None
    
    def get_background_image_url(self, obj):
        try:
            if obj.background_image:
                request = self.context.get('request')
                if request:
                    try:
                        return request.build_absolute_uri(obj.background_image.url)
                    except Exception:
                        # إذا فشل بناء URL، نرجع المسار النسبي
                        return obj.background_image.url if hasattr(obj.background_image, 'url') else None
                return obj.background_image.url if hasattr(obj.background_image, 'url') else None
        except Exception:
            return None
        return None


# ====== Company Registration Serializer ======
class CompanyRegistrationSerializer(serializers.Serializer):
    """Serializer لتسجيل شركة جديدة مع المستخدم المسؤول"""
    # Company Data
    company_name = serializers.CharField(max_length=200, required=True)
    company_logo = serializers.ImageField(required=False, allow_null=True)
    company_license_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    company_email = serializers.EmailField(required=True)
    company_phone = serializers.CharField(max_length=20, required=True)
    company_address = serializers.CharField(required=False, allow_blank=True)
    
    # Admin User Data
    admin_first_name = serializers.CharField(max_length=150, required=True)
    admin_last_name = serializers.CharField(max_length=150, required=True)
    admin_email = serializers.EmailField(required=True)
    admin_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    
    def validate_admin_email(self, value):
        """التحقق من أن البريد الإلكتروني غير مستخدم"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value
    
    def validate_company_email(self, value):
        """التحقق من أن بريد الشركة غير مستخدم"""
        if TenantSettings.objects.filter(company_email=value).exists():
            raise serializers.ValidationError("This company email is already registered.")
        return value


class AdminCreateCompanySerializer(serializers.Serializer):
    """Serializer لإنشاء شركة جديدة من قبل السوبر أدمن"""
    # Company Basic Data
    company_name = serializers.CharField(max_length=200, required=True)
    company_name_en = serializers.CharField(max_length=200, required=False, allow_blank=True)
    company_slug = serializers.SlugField(max_length=200, required=False, allow_blank=True, help_text="Company code (auto-generated if not provided)")
    company_email = serializers.EmailField(required=True)
    company_phone = serializers.CharField(max_length=20, required=True)
    company_license_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    company_country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    company_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    company_address = serializers.CharField(required=False, allow_blank=True)
    
    # Subscription Settings
    subscription_status = serializers.ChoiceField(
        choices=['active', 'suspended', 'expired', 'trial'],
        default='trial'
    )
    subscription_start_date = serializers.DateField(required=False, allow_null=True)
    subscription_end_date = serializers.DateField(required=False, allow_null=True)
    is_trial = serializers.BooleanField(default=True, required=False)
    trial_ends_at = serializers.DateTimeField(required=False, allow_null=True)
    
    # Limits
    max_users = serializers.IntegerField(min_value=1, default=10, required=False)
    max_projects = serializers.IntegerField(min_value=1, default=50, required=False)
    
    # Admin User Data
    admin_first_name = serializers.CharField(max_length=150, required=True)
    admin_last_name = serializers.CharField(max_length=150, required=True)
    admin_email = serializers.EmailField(required=True)
    admin_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    
    def validate_admin_email(self, value):
        """التحقق من أن البريد الإلكتروني غير مستخدم"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value
    
    def validate_company_email(self, value):
        """التحقق من أن بريد الشركة غير مستخدم"""
        if TenantSettings.objects.filter(company_email=value).exists():
            raise serializers.ValidationError("This company email is already registered.")
        return value


# ====== Permission Serializer ======
class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'code', 'name', 'name_en', 'description', 'category', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ====== Role Serializer ======
class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        source='permissions',
        write_only=True,
        required=False
    )
    permission_codes = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'name_en', 'description', 'is_active',
            'permissions', 'permission_ids', 'permission_codes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_permission_codes(self, obj):
        return list(obj.permissions.values_list('code', flat=True))


# ====== User Serializer ======
class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source='role',
        write_only=True,
        required=False,
        allow_null=True
    )
    tenant = TenantSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'phone',
            'is_active', 'is_staff', 'is_superuser',
            'role', 'role_id', 'permissions', 'tenant',
            'date_joined', 'last_login',
            'password',
            'avatar', 'avatar_url',
            'date_of_birth', 'blood_type',
            'emergency_contact_name', 'emergency_contact_phone', 'medical_notes',
            'onboarding_completed'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_superuser', 'tenant']
    
    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None
    
    def get_permissions(self, obj):
        """الحصول على جميع صلاحيات المستخدم"""
        return list(obj.get_all_permissions())
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# ====== User Registration Serializer ======
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'phone', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ====== Login Serializer ======
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


# ====== Workflow Stage Serializer ======
class WorkflowStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStage
        fields = ['id', 'code', 'name', 'name_en', 'description', 'order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ====== Workflow Rule Serializer ======
class WorkflowRuleSerializer(serializers.ModelSerializer):
    stage = WorkflowStageSerializer(read_only=True)
    stage_id = serializers.PrimaryKeyRelatedField(
        queryset=WorkflowStage.objects.all(),
        source='stage',
        write_only=True
    )
    required_permission = PermissionSerializer(read_only=True)
    permission_id = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        source='required_permission',
        write_only=True
    )
    allowed_roles = RoleSerializer(many=True, read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Role.objects.all(),
        source='allowed_roles',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = WorkflowRule
        fields = [
            'id', 'stage', 'stage_id', 'action', 'required_permission', 'permission_id',
            'allowed_roles', 'role_ids', 'description', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ====== Audit Log Serializer ======
class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    stage = WorkflowStageSerializer(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'action', 'model_name', 'object_id',
            'description', 'changes', 'ip_address', 'user_agent',
            'stage', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ====== Profile Serializer ======
class ProfileSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'phone',
            'role', 'permissions',
            'date_joined', 'last_login',
            'avatar', 'avatar_url',
            'date_of_birth', 'blood_type',
            'emergency_contact_name', 'emergency_contact_phone', 'medical_notes',
            'onboarding_completed'
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'last_login']
        extra_kwargs = {
            'username': {'required': False, 'allow_blank': True, 'allow_null': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'phone': {'required': False, 'allow_blank': True},
            'date_of_birth': {'required': False, 'allow_null': True},
            'blood_type': {'required': False, 'allow_blank': True},
            'emergency_contact_name': {'required': False, 'allow_blank': True},
            'emergency_contact_phone': {'required': False, 'allow_blank': True},
            'medical_notes': {'required': False, 'allow_blank': True},
        }
    
    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None
    
    def get_permissions(self, obj):
        return list(obj.get_all_permissions())


# ====== Pending Change Serializer ======
class PendingChangeSerializer(serializers.ModelSerializer):
    """Serializer لـ PendingChange"""
    requested_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PendingChange
        fields = [
            'id', 'requested_by', 'requested_by_name', 'tenant', 'tenant_name',
            'action', 'model_name', 'object_id', 'data', 'old_data',
            'status', 'reviewed_by', 'reviewed_by_name', 'reviewed_at', 'review_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'reviewed_at']
    
    def get_requested_by_name(self, obj):
        return obj.requested_by.get_full_name() if obj.requested_by else None
    
    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() if obj.reviewed_by else None
    
    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else None
