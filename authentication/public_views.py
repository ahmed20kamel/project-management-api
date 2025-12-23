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
    
    # بناء URL للشعار
    logo_url = None
    if settings.company_logo:
        request_scheme = request.scheme
        request_host = request.get_host()
        logo_url = f"{request_scheme}://{request_host}{settings.company_logo.url}"
    
    # بناء URL لصورة الخلفية
    background_image_url = None
    if settings.background_image:
        request_scheme = request.scheme
        request_host = request.get_host()
        background_image_url = f"{request_scheme}://{request_host}{settings.background_image.url}"
    
    return Response({
        'tenant_id': str(tenant.id),
        'tenant_slug': tenant.slug,
        'company_name': settings.company_name or tenant.name,
        'logo': logo_url,
        'background_image': background_image_url,
        'primary_color': settings.primary_color or '#f97316',
        'secondary_color': settings.secondary_color or '#ea580c'
    })

