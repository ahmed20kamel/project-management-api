"""
Custom CSRF Middleware to improve CSRF cookie handling for cross-domain
and skip CSRF for DRF API views (which use JWT authentication)
"""
from django.middleware.csrf import CsrfViewMiddleware
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class CustomCsrfViewMiddleware(CsrfViewMiddleware, MiddlewareMixin):
    """
    Custom CSRF middleware that:
    1. Improves cookie handling for cross-domain
    2. Skips CSRF for DRF API views (they use JWT, not session auth)
    """
    
    def process_view(self, request, callback, callback_args, callback_kwargs):
        # ✅ تخطي CSRF للـ API endpoints (تستخدم JWT)
        if request.path.startswith('/api/'):
            return None  # Skip CSRF check for API endpoints
        
        # ✅ للـ endpoints الأخرى، نستخدم CSRF العادي
        return super().process_view(request, callback, callback_args, callback_kwargs)
    
    def process_response(self, request, response):
        """Improve CSRF cookie handling"""
        response = super().process_response(request, response)
        
        # ✅ تحسين CSRF cookie في الإنتاج
        if not settings.DEBUG and hasattr(response, 'cookies'):
            csrf_cookie_name = getattr(settings, 'CSRF_COOKIE_NAME', 'csrftoken')
            csrf_cookie = response.cookies.get(csrf_cookie_name)
            if csrf_cookie and settings.CSRF_COOKIE_SAMESITE == 'None':
                # ✅ التأكد من أن Secure=True
                csrf_cookie['secure'] = True
                csrf_cookie['samesite'] = 'None'
                # ✅ لا نضيف Domain لأننا نريد أن يعمل على جميع subdomains
        
        return response

