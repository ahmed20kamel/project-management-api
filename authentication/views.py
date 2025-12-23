from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Q
from rest_framework import serializers as drf_serializers

from .models import User, Role, Permission, WorkflowStage, WorkflowRule, AuditLog, Tenant, TenantSettings, PendingChange
from .serializers import (
    UserSerializer, UserRegistrationSerializer, LoginSerializer,
    RoleSerializer, PermissionSerializer,
    WorkflowStageSerializer, WorkflowRuleSerializer,
    AuditLogSerializer, ProfileSerializer,
    CompanyRegistrationSerializer, AdminCreateCompanySerializer,
    TenantSerializer, TenantSettingsSerializer,
    TenantThemeSerializer, PendingChangeSerializer
)
from .utils import (
    log_audit, get_client_ip, is_company_admin, is_staff_user, is_manager,
    requires_approval, create_pending_change, can_access_financial_data,
    can_manage_contracts, can_manage_payments
)


# ====== Company Registration View ======
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_company(request):
    """
    تسجيل شركة جديدة مع المستخدم المسؤول
    """
    serializer = CompanyRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            # 1. إنشاء Tenant
            tenant = Tenant.objects.create(
                name=serializer.validated_data['company_name'],
                is_active=True,
                is_trial=True
            )
            
            # 2. إنشاء TenantSettings
            tenant_settings = TenantSettings.objects.create(
                tenant=tenant,
                company_name=serializer.validated_data['company_name'],
                company_logo=serializer.validated_data.get('company_logo'),
                company_license_number=serializer.validated_data.get('company_license_number', ''),
                company_email=serializer.validated_data['company_email'],
                company_phone=serializer.validated_data['company_phone'],
                company_address=serializer.validated_data.get('company_address', '')
            )
            
            # 3. إنشاء المستخدم المسؤول وربطه بالـ tenant
            admin_user = User.objects.create_user(
                email=serializer.validated_data['admin_email'],
                password=serializer.validated_data['admin_password'],
                first_name=serializer.validated_data['admin_first_name'],
                last_name=serializer.validated_data['admin_last_name'],
                tenant=tenant,
                is_staff=True,  # Admin user
                is_active=True
            )
            
            # 4. إنشاء Role "Admin" افتراضياً إذا لم يكن موجوداً
            admin_role, created = Role.objects.get_or_create(
                name='Admin',
                defaults={
                    'name_en': 'Admin',
                    'description': 'مدير النظام',
                    'is_active': True
                }
            )
            admin_user.role = admin_role
            admin_user.save()
            
            # 5. تسجيل Audit Log
            log_audit(
                user=admin_user,
                action='create',
                model_name='Tenant',
                object_id=tenant.id,
                description=f'Company registered: {tenant.name}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # 6. إرجاع البيانات مع JWT Token
            refresh = RefreshToken.for_user(admin_user)
            
            return Response({
                'message': 'Company registered successfully',
                'tenant': TenantSerializer(tenant).data,
                'settings': TenantSettingsSerializer(tenant_settings, context={'request': request}).data,
                'admin_user': UserSerializer(admin_user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to register company: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ====== Admin Create Company View ======
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_create_company(request):
    """
    إنشاء شركة جديدة من قبل السوبر أدمن
    """
    if not request.user.is_superuser:
        return Response(
            {'error': 'Only superusers can create companies.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Log incoming data for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Admin create company request data: {request.data}")
    
    serializer = AdminCreateCompanySerializer(data=request.data)
    if serializer.is_valid():
        try:
            # 1. إنشاء Tenant
            # إذا تم توفير slug، نستخدمه، وإلا سيتم توليده تلقائياً في save()
            tenant_data = {
                'name': serializer.validated_data['company_name'],
                'is_active': True,
                'is_trial': serializer.validated_data.get('is_trial', True),
                'trial_ends_at': serializer.validated_data.get('trial_ends_at')
            }
            # إذا تم توفير slug يدوياً
            if serializer.validated_data.get('company_slug'):
                tenant_data['slug'] = serializer.validated_data['company_slug']
            
            tenant = Tenant.objects.create(**tenant_data)
            
            # 2. إنشاء TenantSettings
            tenant_settings = TenantSettings.objects.create(
                tenant=tenant,
                company_name=serializer.validated_data['company_name'],
                company_email=serializer.validated_data['company_email'],
                company_phone=serializer.validated_data['company_phone'],
                company_license_number=serializer.validated_data.get('company_license_number', ''),
                company_address=serializer.validated_data.get('company_address', ''),
                max_users=serializer.validated_data.get('max_users', 10),
                max_projects=serializer.validated_data.get('max_projects', 50),
                subscription_status=serializer.validated_data.get('subscription_status', 'trial'),
                subscription_start_date=serializer.validated_data.get('subscription_start_date'),
                subscription_end_date=serializer.validated_data.get('subscription_end_date')
            )
            
            # 3. إنشاء المستخدم الرئيسي وربطه بالـ tenant
            # البحث عن دور company_super_admin
            company_super_admin_role, _ = Role.objects.get_or_create(
                name='company_super_admin',
                defaults={
                    'name_en': 'Company Super Admin',
                    'description': 'مدير الشركة الداخلي',
                    'is_active': True
                }
            )
            
            admin_user = User.objects.create_user(
                email=serializer.validated_data['admin_email'],
                password=serializer.validated_data['admin_password'],
                first_name=serializer.validated_data['admin_first_name'],
                last_name=serializer.validated_data['admin_last_name'],
                tenant=tenant,
                role=company_super_admin_role,
                is_staff=True,
                is_active=True,
                onboarding_completed=False  # لم يكمل Onboarding بعد
            )
            
            # 4. تسجيل Audit Log
            log_audit(
                user=request.user,
                action='create',
                model_name='Tenant',
                object_id=tenant.id,
                description=f'Company created by admin: {tenant.name}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'message': 'Company created successfully',
                'tenant': TenantSerializer(tenant).data,
                'settings': TenantSettingsSerializer(tenant_settings, context={'request': request}).data,
                'admin_user': UserSerializer(admin_user).data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create company: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ====== Tenant ViewSet ======
class TenantViewSet(viewsets.ModelViewSet):
    """ViewSet للـ Tenant - السوبر أدمن يمكنه التعديل، المستخدمون العاديون قراءة فقط"""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # المستخدمون العاديون يرون فقط tenant الخاص بهم
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                return Tenant.objects.filter(id=self.request.user.tenant.id)
            return Tenant.objects.none()
        return Tenant.objects.all()
    
    def get_serializer_class(self):
        return TenantSerializer
    
    def update(self, request, *args, **kwargs):
        """تحديث Tenant - فقط السوبر أدمن يمكنه التعديل"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'فقط السوبر أدمن يمكنه تعديل بيانات الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """تحديث جزئي لـ Tenant - فقط السوبر أدمن يمكنه التعديل"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'فقط السوبر أدمن يمكنه تعديل بيانات الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """حذف Tenant - فقط السوبر أدمن يمكنه الحذف"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'فقط السوبر أدمن يمكنه حذف الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def current(self, request):
        """الحصول على tenant الحالي للمستخدم"""
        if hasattr(request.user, 'tenant') and request.user.tenant:
            serializer = self.get_serializer(request.user.tenant)
            return Response(serializer.data)
        return Response(
            {'error': 'User is not associated with any tenant'},
            status=status.HTTP_404_NOT_FOUND
        )


# ====== Tenant Settings ViewSet ======
class TenantSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة إعدادات الشركة"""
    queryset = TenantSettings.objects.all()
    serializer_class = TenantSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def get_queryset(self):
        # Superuser يمكنه رؤية جميع الإعدادات
        if self.request.user.is_superuser:
            return TenantSettings.objects.all()
        
        # Company Super Admin يمكنه رؤية إعدادات شركته فقط
        if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            # التحقق من أن المستخدم هو Company Super Admin
            if self.request.user.role and self.request.user.role.name == 'company_super_admin':
                return TenantSettings.objects.filter(tenant=self.request.user.tenant)
            # المستخدمون العاديون لا يمكنهم رؤية الإعدادات
            return TenantSettings.objects.none()
        return TenantSettings.objects.none()
    
    def get_serializer_class(self):
        # Superuser يمكنه تعديل جميع الحقول بما فيها Limits
        if self.request.user.is_superuser:
            return TenantSettingsSerializer
        # Company Super Admin يمكنه تعديل الإعدادات العامة فقط (ليس Limits)
        return TenantSettingsSerializer
    
    @action(detail=False, methods=['get', 'patch', 'put'], permission_classes=[permissions.IsAuthenticated])
    def current(self, request):
        """الحصول على أو تحديث إعدادات الشركة الحالية"""
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            return Response(
                {'error': 'User is not associated with any tenant'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            settings = TenantSettings.objects.get(tenant=request.user.tenant)
        except TenantSettings.DoesNotExist:
            return Response(
                {'error': 'Tenant settings not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'GET':
            serializer = self.get_serializer(settings, context={'request': request})
            return Response(serializer.data)
        elif request.method in ['PATCH', 'PUT']:
            # التحقق من الصلاحيات: فقط Company Super Admin يمكنه التعديل
            if not request.user.is_superuser:
                if not is_company_admin(request.user):
                    return Response(
                        {'error': 'Only company super admin can update company settings'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # منع تعديل الحقول المحمية (email, subscription info)
            protected_fields = ['company_email', 'max_users', 'max_projects', 
                               'subscription_start_date', 'subscription_end_date', 'subscription_status']
            for field in protected_fields:
                if field in request.data:
                    del request.data[field]
            
            # تحديث الإعدادات
            serializer = self.get_serializer(
                settings,
                data=request.data,
                partial=(request.method == 'PATCH'),
                context={'request': request}
            )
            if serializer.is_valid():
                # ✅ حفظ البيانات
                instance = serializer.save()
                
                # ✅ التأكد من حفظ البيانات في قاعدة البيانات
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"TenantSettings updated for tenant {settings.tenant.id}")
                logger.info(f"Company Logo: {instance.company_logo}")
                logger.info(f"Primary Color: {instance.primary_color}")
                logger.info(f"Secondary Color: {instance.secondary_color}")
                
                # ✅ إعادة تحميل من قاعدة البيانات للتأكد
                instance.refresh_from_db()
                
                log_audit(
                    user=request.user,
                    action='edit',
                    model_name='TenantSettings',
                    object_id=settings.tenant.id,
                    description='Updated tenant settings',
                    ip_address=get_client_ip(request)
                )
                
                # ✅ إعادة البيانات المحدثة
                response_serializer = self.get_serializer(instance, context={'request': request})
                return Response(response_serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def theme(self, request):
        """الحصول على Theme الشركة (للقراءة فقط) - متاح لجميع المستخدمين داخل الشركة"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Super Admin لا يحتاج Theme - نرجع theme افتراضي
            if request.user.is_superuser:
                logger.info("Super admin requested theme, returning default")
                return Response({
                    'tenant_id': None,
                    'company_name': 'System Admin',
                    'logo_url': None,
                    'background_image_url': None,
                    'primary_color': '#f97316',
                    'secondary_color': '#ea580c'
                })
            
            # التحقق من وجود tenant
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                logger.warning(f"User {request.user.id} has no tenant, returning default theme")
                return Response({
                    'tenant_id': None,
                    'company_name': '',
                    'logo_url': None,
                    'background_image_url': None,
                    'primary_color': '#f97316',
                    'secondary_color': '#ea580c'
                })
            
            # محاولة الحصول على TenantSettings
            # Theme الشركة متاح لجميع المستخدمين داخل الشركة (Manager, Staff User, Company Super Admin)
            try:
                # ✅ إعادة تحميل من قاعدة البيانات للتأكد من أحدث البيانات
                settings = TenantSettings.objects.select_related('tenant').get(tenant=request.user.tenant)
                
                # ✅ Logging للتأكد من البيانات
                logger.info(f"Loading theme for tenant {request.user.tenant.id}")
                
                serializer = TenantThemeSerializer(settings, context={'request': request})
                theme_data = serializer.data
                
                # ✅ التأكد من وجود tenant_id
                if not theme_data.get('tenant_id'):
                    theme_data['tenant_id'] = str(request.user.tenant.id)
                
                # ✅ التأكد من وجود company_name
                if not theme_data.get('company_name') and request.user.tenant:
                    theme_data['company_name'] = request.user.tenant.name or ''
                
                return Response(theme_data)
            except TenantSettings.DoesNotExist:
                # إذا لم تكن هناك إعدادات، نعيد Theme افتراضي
                logger.warning(f"TenantSettings not found for tenant {request.user.tenant.id}, returning default theme")
                return Response({
                    'tenant_id': str(request.user.tenant.id),
                    'company_name': request.user.tenant.name if request.user.tenant else '',
                    'logo_url': None,
                    'background_image_url': None,
                    'primary_color': '#f97316',
                    'secondary_color': '#ea580c'
                })
            except Exception as inner_e:
                logger.error(f"Error in theme endpoint inner try: {str(inner_e)}", exc_info=True)
                # في حالة خطأ، نعيد Theme افتراضي
                return Response({
                    'tenant_id': str(request.user.tenant.id) if request.user.tenant else None,
                    'company_name': request.user.tenant.name if request.user.tenant else '',
                    'logo_url': None,
                    'background_image_url': None,
                    'primary_color': '#f97316',
                    'secondary_color': '#ea580c'
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error loading theme: {str(e)}", exc_info=True)
            # في حالة أي خطأ، نرجع theme افتراضي بدلاً من 500
            return Response({
                'tenant_id': str(request.user.tenant.id) if hasattr(request.user, 'tenant') and request.user.tenant else None,
                'company_name': request.user.tenant.name if hasattr(request.user, 'tenant') and request.user.tenant else '',
                'logo_url': None,
                'background_image_url': None,
                'primary_color': '#f97316',
                'secondary_color': '#ea580c'
            })
    
    def perform_update(self, serializer):
        """تسجيل Audit Log عند تحديث الإعدادات"""
        instance = serializer.save()
        log_audit(
            user=self.request.user,
            action='edit',
            model_name='TenantSettings',
            object_id=instance.tenant.id,
            description='Updated tenant settings',
            ip_address=get_client_ip(self.request)
        )


# ====== Custom JWT Token View ======
class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = authenticate(request, email=email, password=password)
            if user and user.is_active:
                refresh = RefreshToken.for_user(user)
                
                # تحديث last_login
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                # تسجيل عملية الدخول
                log_audit(
                    user=user,
                    action='login',
                    model_name='User',
                    object_id=user.id,
                    description=f'User logged in',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                # تحديد نوع المستخدم
                user_role = 'user'
                if user.is_superuser:
                    user_role = 'super_admin'
                elif user.is_staff and user.role and user.role.name:
                    try:
                        role_name = user.role.name.lower()
                        if role_name == 'company_super_admin':
                            user_role = 'company_super_admin'
                        elif 'admin' in role_name:
                            user_role = 'tenant_admin'
                        else:
                            user_role = 'user'
                    except (AttributeError, Exception):
                        user_role = 'tenant_admin' if user.is_staff else 'user'
                elif user.is_staff:
                    user_role = 'tenant_admin'
                
                # إعداد بيانات الاستجابة
                try:
                    user_data = UserSerializer(user, context={'request': request}).data
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error serializing user: {str(e)}", exc_info=True)
                    # في حالة الخطأ، نعيد بيانات أساسية فقط
                    user_data = {
                        'id': user.id,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_superuser': user.is_superuser,
                        'is_staff': user.is_staff,
                        'onboarding_completed': getattr(user, 'onboarding_completed', False),
                        'tenant': None
                    }
                    if user.tenant:
                        user_data['tenant'] = {
                            'id': str(user.tenant.id),
                            'name': user.tenant.name,
                            'slug': user.tenant.slug  # إضافة slug
                        }
                
                response_data = {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': user_data,
                    'role': user_role,
                    'is_super_admin': user.is_superuser,
                }
                
                # إضافة tenant_id و tenant_slug إذا كان المستخدم تابع لشركة
                if user.tenant:
                    response_data['tenant_id'] = str(user.tenant.id)
                    response_data['tenant_slug'] = user.tenant.slug
                else:
                    response_data['tenant_id'] = None
                    response_data['tenant_slug'] = None
                
                return Response(response_data)
            else:
                return Response(
                    {'error': 'Invalid credentials or inactive account'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ====== User ViewSet ======
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def get_queryset(self):
        """تصفية المستخدمين حسب tenant"""
        queryset = User.objects.all()
        
        # Superuser يمكنه رؤية جميع المستخدمين
        if self.request.user.is_superuser:
            return queryset
        
        # تصفية حسب tenant
        if hasattr(self.request, 'tenant') and self.request.tenant:
            queryset = queryset.filter(tenant=self.request.tenant)
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        else:
            queryset = queryset.none()
        
        # فقط Company Super Admin يمكنه رؤية جميع المستخدمين في tenant
        if not self.request.user.is_superuser:
            if not (self.request.user.role and self.request.user.role.name == 'company_super_admin'):
                # المستخدمون العاديون لا يمكنهم رؤية جميع المستخدمين في tenant
                queryset = queryset.filter(id=self.request.user.id)
        
        return queryset
    
    def perform_create(self, serializer):
        """ربط المستخدم الجديد بـ tenant المستخدم الحالي والتحقق من Limits"""
        # التحقق من الصلاحيات: فقط Company Super Admin يمكنه إنشاء مستخدمين
        if not self.request.user.is_superuser:
            if not is_company_admin(self.request.user):
                raise drf_serializers.ValidationError({
                    'error': 'Only company super admin can create users'
                })
        
        tenant = None
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            tenant = self.request.user.tenant
        
        # التحقق من Limits (فقط للمستخدمين التابعين لشركة)
        if tenant and not self.request.user.is_superuser:
            try:
                settings = tenant.settings
                # حساب عدد المستخدمين الحاليين
                current_users_count = User.objects.filter(tenant=tenant, is_active=True).count()
                
                # التحقق من الحد الأقصى
                if current_users_count >= settings.max_users:
                    raise drf_serializers.ValidationError({
                        'error': f'تم الوصول للحد الأقصى لعدد المستخدمين ({settings.max_users}). يرجى التواصل مع مدير النظام لزيادة الحد.'
                    })
                
                # التحقق من حالة الاشتراك
                if settings.subscription_status in ['suspended', 'expired']:
                    raise drf_serializers.ValidationError({
                        'error': f'لا يمكن إضافة مستخدمين. حالة الاشتراك: {settings.get_subscription_status_display()}'
                    })
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نسمح بإنشاء المستخدم
        
        # تحديد حالة onboarding_completed
        # Onboarding مخصص فقط لـ Company Super Admin في أول تسجيل دخول
        # جميع المستخدمين الآخرين (Manager, Staff User) يجب أن يكون onboarding_completed = True
        role_id = serializer.validated_data.get('role_id') or serializer.validated_data.get('role')
        if role_id:
            from .models import Role
            try:
                role = Role.objects.get(pk=role_id)
                # فقط Company Super Admin يحتاج Onboarding
                if role.name == 'company_super_admin':
                    # إذا كان المستخدم الجديد هو Company Super Admin، نترك onboarding_completed كما هو (False افتراضياً)
                    # لكن يجب التأكد من أن الشركة لم تكمل Onboarding بعد
                    pass
                else:
                    # Manager و Staff User لا يحتاجون Onboarding
                    serializer.validated_data['onboarding_completed'] = True
            except Role.DoesNotExist:
                pass
        
        serializer.save(tenant=tenant)
    
    def perform_update(self, serializer):
        """التحقق من الصلاحيات قبل التحديث"""
        instance = serializer.instance
        
        # Superuser يمكنه تعديل أي مستخدم
        if self.request.user.is_superuser:
            # التحقق من الدور إذا تم تحديثه
            role_id = serializer.validated_data.get('role_id') or serializer.validated_data.get('role')
            if role_id:
                from .models import Role
                try:
                    role = Role.objects.get(pk=role_id)
                    # Super Admin يمكنه تعيين أي دور
                    pass
                except Role.DoesNotExist:
                    raise drf_serializers.ValidationError({
                        'error': 'الدور المحدد غير موجود'
                    })
            serializer.save()
            return
        
        # Company Super Admin يمكنه تعديل المستخدمين في tenant الخاص به فقط
        if self.request.user.role and self.request.user.role.name == 'company_super_admin':
            if instance.tenant != self.request.user.tenant:
                raise drf_serializers.ValidationError({
                    'error': 'You can only update users in your own company'
                })
            
            # التحقق من أن الدور المحدد هو من الأدوار الخاصة بالشركة فقط
            role_id = serializer.validated_data.get('role_id') or serializer.validated_data.get('role')
            if role_id:
                from .models import Role
                try:
                    role = Role.objects.get(pk=role_id)
                    # التأكد من أن الدور هو من الأدوار الخاصة بالشركة
                    if role.name not in ['company_super_admin', 'Manager', 'staff_user']:
                        raise drf_serializers.ValidationError({
                            'error': 'يمكن تعيين الأدوار الخاصة بالشركة فقط (مدير الشركة، مدير المشاريع، أو موظف)'
                        })
                except Role.DoesNotExist:
                    raise drf_serializers.ValidationError({
                        'error': 'الدور المحدد غير موجود'
                    })
            
            serializer.save()
            return
        
        # المستخدمون العاديون يمكنهم تعديل بياناتهم فقط
        if instance.id != self.request.user.id:
            raise drf_serializers.ValidationError({
                'error': 'You can only update your own profile'
            })
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """التحقق من الصلاحيات قبل الحذف"""
        # Superuser يمكنه حذف أي مستخدم
        if self.request.user.is_superuser:
            instance.delete()
            return
        
        # Company Super Admin يمكنه حذف المستخدمين في tenant الخاص به فقط
        if is_company_admin(self.request.user):
            if instance.tenant != self.request.user.tenant:
                raise drf_serializers.ValidationError({
                    'error': 'You can only delete users in your own company'
                })
            # منع حذف نفسه
            if instance.id == self.request.user.id:
                raise drf_serializers.ValidationError({
                    'error': 'You cannot delete your own account'
                })
            instance.delete()
            return
        
        # المستخدمون العاديون لا يمكنهم حذف أي مستخدم
        raise drf_serializers.ValidationError({
            'error': 'You do not have permission to delete users'
        })
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def profile(self, request):
        """الحصول على بيانات المستخدم الحالي"""
        serializer = ProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        """تحديث بيانات المستخدم الحالي"""
        # التحقق من أن تحديث onboarding_completed مسموح فقط لـ Company Super Admin
        if 'onboarding_completed' in request.data:
            if not is_company_admin(request.user) and not request.user.is_superuser:
                return Response(
                    {'error': 'Only company super admin can update onboarding status'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            log_audit(
                user=request.user,
                action='edit',
                model_name='User',
                object_id=request.user.id,
                description='User updated profile',
                ip_address=get_client_ip(request)
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def upload_avatar(self, request):
        """رفع صورة المستخدم"""
        if 'avatar' not in request.FILES:
            return Response(
                {'error': 'No avatar file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        user.avatar = request.FILES['avatar']
        user.save(update_fields=['avatar'])
        
        serializer = ProfileSerializer(user, context={'request': request})
        log_audit(
            user=user,
            action='edit',
            model_name='User',
            object_id=user.id,
            description='User uploaded avatar',
            ip_address=get_client_ip(request)
        )
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated])
    def delete_avatar(self, request):
        """حذف صورة المستخدم"""
        user = request.user
        if user.avatar:
            user.avatar.delete()
            user.avatar = None
            user.save(update_fields=['avatar'])
            
            log_audit(
                user=user,
                action='edit',
                model_name='User',
                object_id=user.id,
                description='User deleted avatar',
                ip_address=get_client_ip(request)
            )
            
            return Response({'message': 'Avatar deleted successfully'})
        return Response(
            {'error': 'No avatar to delete'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """تسجيل مستخدم جديد"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            log_audit(
                user=user,
                action='create',
                model_name='User',
                object_id=user.id,
                description='New user registered',
                ip_address=get_client_ip(request)
            )
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """تسجيل الخروج"""
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            log_audit(
                user=request.user,
                action='logout',
                model_name='User',
                object_id=request.user.id,
                description='User logged out',
                ip_address=get_client_ip(request)
            )
            return Response({'message': 'Successfully logged out'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ====== Role ViewSet ======
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Super Admin (Global) يمكنه رؤية جميع الأدوار
        if self.request.user.is_superuser:
            return Role.objects.all()
        
        # Company Admin يمكنه رؤية الأدوار الخاصة بالشركة فقط
        if is_company_admin(self.request.user):
            # فقط الأدوار الخاصة بالشركة: company_super_admin و Manager و staff_user
            return Role.objects.filter(
                is_active=True,
                name__in=['company_super_admin', 'Manager', 'staff_user']
            )
        
        # Staff User يمكنه رؤية الأدوار الخاصة بالشركة فقط (للاختيار عند إنشاء مستخدمين)
        if is_staff_user(self.request.user):
            # Staff User لا يمكنه إنشاء مستخدمين، لكن يمكنه رؤية الأدوار للعرض فقط
            return Role.objects.filter(
                is_active=True,
                name__in=['company_super_admin', 'Manager', 'staff_user']
            )
        
        # المستخدمون العاديون لا يمكنهم رؤية الأدوار
        return Role.objects.none()
    
    def perform_create(self, serializer):
        instance = serializer.save()
        log_audit(
            user=self.request.user,
            action='create',
            model_name='Role',
            object_id=instance.id,
            description=f'Created role: {instance.name}',
            ip_address=get_client_ip(self.request)
        )
    
    def perform_update(self, serializer):
        instance = serializer.save()
        log_audit(
            user=self.request.user,
            action='edit',
            model_name='Role',
            object_id=instance.id,
            description=f'Updated role: {instance.name}',
            ip_address=get_client_ip(self.request)
        )


# ====== Permission ViewSet ======
class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # فقط Staff يمكنهم إدارة الصلاحيات
        if not self.request.user.is_staff:
            return Permission.objects.none()
        return Permission.objects.all()
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """الحصول على الصلاحيات مصنفة حسب الفئة"""
        permissions = Permission.objects.all().order_by('category', 'code')
        categories = {}
        for perm in permissions:
            if perm.category not in categories:
                categories[perm.category] = []
            categories[perm.category].append(PermissionSerializer(perm).data)
        return Response(categories)


# ====== Workflow Stage ViewSet ======
class WorkflowStageViewSet(viewsets.ModelViewSet):
    queryset = WorkflowStage.objects.all()
    serializer_class = WorkflowStageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # فقط Staff يمكنهم إدارة المراحل
        if not self.request.user.is_staff:
            return WorkflowStage.objects.filter(is_active=True)
        return WorkflowStage.objects.all()


# ====== Workflow Rule ViewSet ======
class WorkflowRuleViewSet(viewsets.ModelViewSet):
    queryset = WorkflowRule.objects.all()
    serializer_class = WorkflowRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # فقط Staff يمكنهم إدارة القواعد
        if not self.request.user.is_staff:
            return WorkflowRule.objects.filter(is_active=True)
        return WorkflowRule.objects.all()
    
    @action(detail=False, methods=['get'])
    def by_stage(self, request):
        """الحصول على قواعد مرحلة معينة"""
        stage_id = request.query_params.get('stage_id')
        if not stage_id:
            return Response({'error': 'stage_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        rules = WorkflowRule.objects.filter(stage_id=stage_id, is_active=True)
        serializer = self.get_serializer(rules, many=True)
        return Response(serializer.data)


# ====== Audit Log ViewSet ======
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # المستخدمون العاديون يرون فقط سجلاتهم
        if not self.request.user.is_staff:
            return AuditLog.objects.filter(user=self.request.user)
        return AuditLog.objects.all()
    
    @action(detail=False, methods=['get'])
    def by_model(self, request):
        """الحصول على سجلات Audit لنموذج معين"""
        model_name = request.query_params.get('model_name')
        object_id = request.query_params.get('object_id')
        
        queryset = self.get_queryset()
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# ====== Pending Change ViewSet ======
class PendingChangeViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة التعديلات المعلقة"""
    queryset = PendingChange.objects.all()
    serializer_class = PendingChangeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """تصفية التعديلات حسب tenant المستخدم"""
        queryset = PendingChange.objects.all()
        
        # Super Admin يمكنه رؤية جميع التعديلات
        if self.request.user.is_superuser:
            return queryset
        
        # Company Admin يمكنه رؤية التعديلات في شركته فقط
        if is_company_admin(self.request.user):
            if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                return queryset.filter(tenant=self.request.user.tenant)
        
        # Staff User يمكنه رؤية التعديلات التي طلبها فقط
        if is_staff_user(self.request.user):
            return queryset.filter(requested_by=self.request.user)
        
        return queryset.none()
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """الموافقة على تعديل معلق"""
        from django.utils import timezone
        import json
        
        pending_change = self.get_object()
        
        # التحقق من الصلاحيات: Company Admin و Manager يمكنهم الموافقة
        if not request.user.is_superuser:
            if not (is_company_admin(request.user) or is_manager(request.user)):
                return Response(
                    {'error': 'Only company admin or manager can approve changes'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # التحقق من أن التعديل في نفس tenant
        if not request.user.is_superuser:
            if pending_change.tenant != request.user.tenant:
                return Response(
                    {'error': 'You can only approve changes in your own company'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # التحقق من أن التعديل في حالة pending
        if pending_change.status != 'pending':
            return Response(
                {'error': f'Change is already {pending_change.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # تطبيق التعديل بناءً على نوع العملية
            if pending_change.action == 'create':
                # إنشاء كائن جديد
                model_class = self._get_model_class(pending_change.model_name)
                if model_class:
                    instance = model_class.objects.create(**pending_change.data)
                    object_id = str(instance.id)
                else:
                    return Response(
                        {'error': f'Model {pending_change.model_name} not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif pending_change.action == 'update':
                # تحديث كائن موجود
                model_class = self._get_model_class(pending_change.model_name)
                if model_class:
                    instance = model_class.objects.get(pk=pending_change.object_id)
                    for key, value in pending_change.data.items():
                        setattr(instance, key, value)
                    instance.save()
                    object_id = str(instance.id)
                else:
                    return Response(
                        {'error': f'Model {pending_change.model_name} not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif pending_change.action == 'delete':
                # حذف كائن
                model_class = self._get_model_class(pending_change.model_name)
                if model_class:
                    instance = model_class.objects.get(pk=pending_change.object_id)
                    instance.delete()
                    object_id = pending_change.object_id
                else:
                    return Response(
                        {'error': f'Model {pending_change.model_name} not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # تحديث حالة PendingChange
            pending_change.status = 'approved'
            pending_change.reviewed_by = request.user
            pending_change.reviewed_at = timezone.now()
            pending_change.save()
            
            # تسجيل Audit Log
            log_audit(
                user=request.user,
                action='approve',
                model_name=pending_change.model_name,
                object_id=object_id,
                description=f'Approved {pending_change.action} request by {pending_change.requested_by.email}',
                ip_address=get_client_ip(request),
                changes={'pending_change_id': pending_change.id}
            )
            
            return Response({
                'message': 'Change approved successfully',
                'pending_change': PendingChangeSerializer(pending_change).data
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to apply change: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """رفض تعديل معلق"""
        from django.utils import timezone
        
        pending_change = self.get_object()
        
        # التحقق من الصلاحيات: Company Admin و Manager يمكنهم الرفض
        if not request.user.is_superuser:
            if not (is_company_admin(request.user) or is_manager(request.user)):
                return Response(
                    {'error': 'Only company admin or manager can reject changes'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # التحقق من أن التعديل في نفس tenant
        if not request.user.is_superuser:
            if pending_change.tenant != request.user.tenant:
                return Response(
                    {'error': 'You can only reject changes in your own company'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # التحقق من أن التعديل في حالة pending
        if pending_change.status != 'pending':
            return Response(
                {'error': f'Change is already {pending_change.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # الحصول على ملاحظات الرفض
        review_notes = request.data.get('review_notes', '')
        
        # تحديث حالة PendingChange
        pending_change.status = 'rejected'
        pending_change.reviewed_by = request.user
        pending_change.reviewed_at = timezone.now()
        pending_change.review_notes = review_notes
        pending_change.save()
        
        # تسجيل Audit Log
        log_audit(
            user=request.user,
            action='reject',
            model_name=pending_change.model_name,
            object_id=pending_change.object_id,
            description=f'Rejected {pending_change.action} request by {pending_change.requested_by.email}',
            ip_address=get_client_ip(request),
            changes={'pending_change_id': pending_change.id, 'notes': review_notes}
        )
        
        return Response({
            'message': 'Change rejected successfully',
            'pending_change': PendingChangeSerializer(pending_change).data
        })
    
    def _get_model_class(self, model_name):
        """الحصول على Model Class من اسم النموذج"""
        # Mapping للنماذج
        model_mapping = {
            'Project': 'projects.models.Project',
            'SitePlan': 'projects.models.SitePlan',
            'BuildingLicense': 'projects.models.BuildingLicense',
            'Contract': 'projects.models.Contract',
            'Awarding': 'projects.models.Awarding',
            'Payment': 'projects.models.Payment',
        }
        
        if model_name in model_mapping:
            module_path, class_name = model_mapping[model_name].rsplit('.', 1)
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        
        return None

