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


def can_submit_project(user, project):
    """التحقق من صلاحية المستخدم لإرسال المشروع للموافقة"""
    # فقط المستخدم العادي (User/Staff) يمكنه الإرسال
    if user.is_superuser:
        return False  # Super Admin لا يرسل، يعتمد فقط
    
    if is_company_admin(user):
        return False  # Company Admin لا يرسل، يعتمد فقط
    
    if is_manager(user):
        return False  # Manager لا يرسل، يوافق على المراحل فقط
    
    # Staff User / User العادي يمكنه الإرسال
    # السماح للمستخدم العادي بإرسال المشروع إذا كان في حالة draft (حتى بدون current_stage)
    if project.approval_status == 'draft':
        return True
    # إذا كان هناك current_stage، نتحقق من workflow permission أيضاً
    if project.current_stage:
        return check_workflow_permission(user, project.current_stage, 'submit')
    
    return False


def can_approve_stage(user, project):
    """التحقق من صلاحية المستخدم للموافقة على مرحلة (Manager)"""
    if user.is_superuser:
        return False  # Super Admin يستخدم final_approve
    
    if is_company_admin(user):
        return False  # Company Admin يستخدم final_approve
    
    # فقط Manager يمكنه الموافقة على المرحلة
    # السماح للمدير بالموافقة إذا كان المشروع في حالة pending (حتى بدون current_stage)
    if is_manager(user):
        # إذا كان المشروع في حالة pending، المدير يمكنه الموافقة
        if project.approval_status == 'pending':
            return True
        # إذا كان هناك current_stage، نتحقق من workflow permission أيضاً
        if project.current_stage:
            return check_workflow_permission(user, project.current_stage, 'approve')
    
    return False


def can_final_approve(user, project):
    """التحقق من صلاحية المستخدم للاعتماد النهائي (Super Admin / Company Super Admin)"""
    if user.is_superuser:
        return True  # Super Admin يمكنه الاعتماد النهائي دائماً
    
    if is_company_admin(user):
        return True  # Company Super Admin يمكنه الاعتماد النهائي
    
    return False


def can_edit_project(user, project):
    """التحقق من صلاحية تعديل المشروع"""
    # إذا كان المشروع معتمد نهائياً، لا يمكن التعديل إلا من Super Admin
    if project.is_final_approved:
        return user.is_superuser or is_company_admin(user)
    
    # إذا كان المشروع في حالة pending، لا يمكن التعديل إلا من الشخص الذي أرسله
    if project.approval_status == 'pending':
        # يمكن للمدير أو Super Admin التعديل حتى في حالة pending
        if is_manager(user) or user.is_superuser or is_company_admin(user):
            return True
        # المستخدم العادي يمكنه التعديل فقط إذا كان هو من أرسل المشروع
        # (سنحتاج إضافة created_by field لاحقاً)
        return False
    
    # في حالة draft أو approved، يمكن التعديل حسب الصلاحيات العادية
    if user.is_superuser or is_company_admin(user):
        return True
    
    if is_manager(user):
        return True
    
    # User العادي يمكنه التعديل في حالة draft
    if project.approval_status == 'draft':
        if project.current_stage:
            return check_workflow_permission(user, project.current_stage, 'edit')
    
    return False


def can_create_project(user):
    """التحقق من صلاحية إنشاء مشروع جديد"""
    # جميع المستخدمين المصرح لهم يمكنهم إنشاء مشاريع
    if user.is_superuser:
        return True
    
    if is_company_admin(user):
        return True
    
    if is_manager(user):
        return True
    
    # User العادي يمكنه إنشاء مشروع (لكن يحتاج موافقة)
    return True