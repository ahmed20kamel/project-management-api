"""
Public API Views - لا تحتاج authentication
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Tenant, TenantSettings


@api_view(['GET'])
@permission_classes([AllowAny])
def get_company_info(request, tenant_slug):
    """
    API عامة للحصول على معلومات الشركة من slug
    GET /api/public/company-info/{tenant_slug}/
    """
    try:
        # البحث عن tenant باستخدام slug (case-insensitive)
        tenant = Tenant.objects.get(slug__iexact=tenant_slug, is_active=True)
    except Tenant.DoesNotExist:
        # محاولة البحث بدون case-insensitive كـ fallback
        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Company not found or inactive'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    try:
        settings = tenant.settings
    except TenantSettings.DoesNotExist:
        # إذا لم تكن هناك إعدادات، نعيد بيانات أساسية
        return Response({
            'tenant_id': str(tenant.id),
            'tenant_slug': tenant.slug,
            'company_name': tenant.name,
            'logo': None,
            'background_image': None,
            'primary_color': '#f97316',
            'secondary_color': '#ea580c'
        })
    
    # ✅ بناء URL للشعار باستخدام /api/files/ بدلاً من /media/
    logo_url = None
    if settings.company_logo:
        try:
            from projects.serializers import get_file_url
            file_url = get_file_url(settings.company_logo, None)
            if file_url:
                base_url = request.build_absolute_uri('/').rstrip('/')
                logo_url = f"{base_url}/api/files/{file_url.lstrip('/')}"
        except Exception:
            # Fallback: استخدام Django URL
            django_url = settings.company_logo.url
            if django_url.startswith('/media/'):
                relative_path = django_url[7:]
            elif django_url.startswith('media/'):
                relative_path = django_url[6:]
            else:
                relative_path = django_url.lstrip('/')
            base_url = request.build_absolute_uri('/').rstrip('/')
            logo_url = f"{base_url}/api/files/{relative_path}"
    
    # ✅ بناء URL لصورة الخلفية باستخدام /api/files/ بدلاً من /media/
    background_image_url = None
    if settings.background_image:
        try:
            from projects.serializers import get_file_url
            file_url = get_file_url(settings.background_image, None)
            if file_url:
                base_url = request.build_absolute_uri('/').rstrip('/')
                background_image_url = f"{base_url}/api/files/{file_url.lstrip('/')}"
        except Exception:
            # Fallback: استخدام Django URL
            django_url = settings.background_image.url
            if django_url.startswith('/media/'):
                relative_path = django_url[7:]
            elif django_url.startswith('media/'):
                relative_path = django_url[6:]
            else:
                relative_path = django_url.lstrip('/')
            base_url = request.build_absolute_uri('/').rstrip('/')
            background_image_url = f"{base_url}/api/files/{relative_path}"
    
    return Response({
        'tenant_id': str(tenant.id),
        'tenant_slug': tenant.slug,
        'company_name': settings.company_name or tenant.name,
        'logo': logo_url,
        'background_image': background_image_url,
        'primary_color': settings.primary_color or '#f97316',
        'secondary_color': settings.secondary_color or '#ea580c'
    })

