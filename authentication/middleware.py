"""
Multi-Tenant Middleware
يحمل tenant context من المستخدم الحالي
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import Http404


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware لتحميل tenant context من المستخدم الحالي
    """
    
    def process_request(self, request):
        """
        تحميل tenant من المستخدم الحالي
        """
        # إضافة tenant إلى request
        request.tenant = None
        
        # إذا كان المستخدم مسجل دخول
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'tenant') and request.user.tenant:
                request.tenant = request.user.tenant
        
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        التحقق من tenant في View
        """
        # السماح للـ public endpoints (مثل تسجيل الشركة، تسجيل الدخول)
        public_paths = [
            '/api/auth/register-company/',
            '/api/auth/login/',
            '/api/auth/token/refresh/',
        ]
        
        if request.path in public_paths:
            return None
        
        # إذا كان المستخدم مسجل دخول ولكن ليس لديه tenant
        if hasattr(request, 'user') and request.user.is_authenticated:
            if not hasattr(request, 'tenant') or request.tenant is None:
                # السماح للـ superuser فقط
                if not request.user.is_superuser:
                    from rest_framework.response import Response
                    from rest_framework import status
                    return Response(
                        {'error': 'User is not associated with any tenant'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        return None
