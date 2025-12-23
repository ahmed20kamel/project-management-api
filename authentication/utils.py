"""
Utility functions for authentication and permissions
"""
from django.utils import timezone
from .models import User, AuditLog, PendingChange, Tenant


def get_client_ip(request):
    """الحصول على IP address للعميل"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(user, action, model_name, object_id=None, description='', ip_address=None, user_agent='', stage=None, changes=None):
    """تسجيل عملية في Audit Log"""
    # تحويل object_id إلى string إذا كان UUID أو integer
    object_id_str = str(object_id) if object_id is not None else None
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id_str,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        stage=stage,
        changes=changes or {}
    )


def check_workflow_permission(user, stage, action):
    """التحقق من صلاحية المستخدم لتنفيذ إجراء في مرحلة معينة"""
    if user.is_superuser:
        return True
    
    from .models import WorkflowRule
    try:
        rule = WorkflowRule.objects.get(stage=stage, action=action, is_active=True)
        
        # التحقق من الصلاحية
        if user.role and rule.required_permission:
            if user.has_permission(rule.required_permission.code):
                return True
        
        # التحقق من الدور المسموح
        if rule.allowed_roles.exists():
            if user.role and user.role in rule.allowed_roles.all():
                return True
        
        return False
    except WorkflowRule.DoesNotExist:
        return False


def is_company_admin(user):
    """التحقق من أن المستخدم هو Company Admin"""
    if user.is_superuser:
        return False  # Super Admin ليس Company Admin
    
    return (
        user.role and 
        user.role.name == 'company_super_admin'
    )


def is_staff_user(user):
    """التحقق من أن المستخدم هو Staff User"""
    if user.is_superuser:
        return False
    
    if not user.role:
        return False
    
    return user.role.name == 'staff_user'


def is_manager(user):
    """التحقق من أن المستخدم هو Manager"""
    if user.is_superuser:
        return False
    
    if not user.role:
        return False
    
    return user.role.name == 'Manager'


def requires_approval(user, model_name):
    """التحقق من أن التعديل يحتاج موافقة"""
    # Super Admin و Company Admin لا يحتاجون موافقة
    if user.is_superuser or is_company_admin(user):
        return False
    
    # Staff User يحتاج موافقة لجميع التعديلات
    if is_staff_user(user):
        return True
    
    return False


def create_pending_change(user, action, model_name, object_id, data, old_data=None, tenant=None):
    """إنشاء سجل Pending Change"""
    if not tenant:
        tenant = user.tenant
    
    if not tenant:
        raise ValueError("Tenant is required for pending changes")
    
    pending_change = PendingChange.objects.create(
        requested_by=user,
        tenant=tenant,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        data=data,
        old_data=old_data or {}
    )
    
    return pending_change


def can_access_financial_data(user):
    """التحقق من صلاحية الوصول للبيانات المالية"""
    if user.is_superuser:
        return True
    
    if is_company_admin(user):
        return True
    
    # Manager يمكنه الوصول للبيانات المالية (لإدارة المشاريع)
    if is_manager(user):
        return True
    
    # Staff User لا يمكنه الوصول للبيانات المالية
    return False


def can_manage_contracts(user):
    """التحقق من صلاحية إدارة العقود"""
    if user.is_superuser:
        return True
    
    if is_company_admin(user):
        return True
    
    # Manager يمكنه إدارة العقود (جزء من إدارة المشاريع)
    if is_manager(user):
        return True
    
    # Staff User لا يمكنه إدارة العقود
    return False


def can_manage_payments(user):
    """التحقق من صلاحية إدارة الدفعات"""
    if user.is_superuser:
        return True
    
    if is_company_admin(user):
        return True
    
    # Manager يمكنه إدارة الدفعات (جزء من إدارة المشاريع)
    if is_manager(user):
        return True
    
    # Staff User لا يمكنه إدارة الدفعات
    return False
