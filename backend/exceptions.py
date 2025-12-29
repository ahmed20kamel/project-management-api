"""
Custom Exception Handlers for Django REST Framework
"""
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF
    Provides consistent error responses and handles CSRF errors gracefully
    """
    # ✅ تخطي معالجة Django admin views - دع Django يتعامل معها
    request = context.get('request')
    if request and request.path.startswith('/admin/'):
        return None
    
    # ✅ معالجة CSRF errors بشكل خاص
    if isinstance(exc, PermissionDenied) and 'CSRF' in str(exc):
        logger.warning(f"CSRF verification failed: {exc}")
        return Response(
            {
                'error': True,
                'status_code': 403,
                'detail': 'CSRF verification failed. Please refresh the page and try again.',
                'csrf_error': True,
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # ✅ الحصول على الـ response الافتراضي من DRF
    response = exception_handler(exc, context)
    
    if response is not None:
        # ✅ تحسين error response
        detail = response.data.get('detail', 'An error occurred') if isinstance(response.data, dict) else str(response.data)
        custom_response_data = {
            'error': True,
            'status_code': response.status_code,
            'detail': detail,
        }
        
        # ✅ إضافة تفاصيل إضافية في التطوير
        from django.conf import settings
        if settings.DEBUG:
            custom_response_data['debug'] = {
                'exception_type': type(exc).__name__,
                'message': str(exc),
                'data': response.data,
            }
        
        # ✅ Logging للأخطاء المهمة
        if response.status_code >= 500:
            logger.error(
                f"Server error: {type(exc).__name__} - {str(exc)}",
                exc_info=True,
                extra={'context': context}
            )
        elif response.status_code >= 400:
            logger.warning(
                f"Client error: {type(exc).__name__} - {str(exc)}",
                extra={'context': context}
            )
        
        response.data = custom_response_data
    
    return response

