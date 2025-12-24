"""
Health Check Endpoints
"""
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Basic health check endpoint
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'project-management-api'
    })


def detailed_health_check(request):
    """
    Detailed health check with database and cache status
    """
    health_status = {
        'status': 'healthy',
        'service': 'project-management-api',
        'checks': {}
    }
    
    # ✅ Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['checks']['database'] = 'healthy'
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status['checks']['database'] = 'unhealthy'
        health_status['status'] = 'degraded'
    
    # ✅ Cache check
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            health_status['checks']['cache'] = 'healthy'
        else:
            health_status['checks']['cache'] = 'unhealthy'
            health_status['status'] = 'degraded'
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        health_status['checks']['cache'] = 'unhealthy'
        health_status['status'] = 'degraded'
    
    return JsonResponse(health_status)

