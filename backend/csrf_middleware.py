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
        """Improve CSRF cookie handling with Partitioned attribute"""
        response = super().process_response(request, response)
        
        # ✅ تحسين CSRF cookie في الإنتاج
        if not settings.DEBUG and hasattr(response, 'cookies'):
            csrf_cookie_name = getattr(settings, 'CSRF_COOKIE_NAME', 'csrftoken')
            csrf_cookie = response.cookies.get(csrf_cookie_name)
            if csrf_cookie and settings.CSRF_COOKIE_SAMESITE == 'None':
                # ✅ التأكد من أن Secure=True
                csrf_cookie['secure'] = True
                csrf_cookie['samesite'] = 'None'
                # ✅ إضافة Partitioned attribute لحل تحذير Chrome
                # Note: Django لا يدعم Partitioned مباشرة، لكن يمكن إضافته عبر تعديل Set-Cookie header
                # نستخدم _headers dict لإضافة Partitioned attribute
                if hasattr(response, '_headers'):
                    # البحث عن Set-Cookie header للـ CSRF cookie
                    set_cookie_header = None
                    for header_name, header_value in list(response._headers.items()):
                        if header_name.lower() == 'set-cookie':
                            header_str = str(header_value[1]) if isinstance(header_value, tuple) else str(header_value)
                            if csrf_cookie_name in header_str and 'Partitioned' not in header_str:
                                # إضافة Partitioned إلى Set-Cookie header
                                if '; Secure' in header_str:
                                    header_str = header_str.replace('; Secure', '; Secure; Partitioned')
                                elif '; SameSite=None' in header_str:
                                    header_str = header_str.replace('; SameSite=None', '; SameSite=None; Partitioned')
                                else:
                                    header_str += '; Partitioned'
                                response._headers[header_name] = (header_name, header_str)
                                break
        
        return response

