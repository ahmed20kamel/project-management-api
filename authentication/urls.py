from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, RoleViewSet, PermissionViewSet,
    WorkflowStageViewSet, WorkflowRuleViewSet, AuditLogViewSet,
    CustomTokenObtainPairView,
    TenantViewSet, TenantSettingsViewSet, PendingChangeViewSet,
    register_company, admin_create_company
)
from .public_views import get_company_info

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'workflow-stages', WorkflowStageViewSet, basename='workflow-stage')
router.register(r'workflow-rules', WorkflowRuleViewSet, basename='workflow-rule')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'tenant-settings', TenantSettingsViewSet, basename='tenant-settings')
router.register(r'pending-changes', PendingChangeViewSet, basename='pendingchanges')
router.register(r'pending-changes', PendingChangeViewSet, basename='pending-change')

urlpatterns = [
    path('register-company/', register_company, name='register_company'),
    path('admin/create-company/', admin_create_company, name='admin_create_company'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]

# Public API (لا تحتاج authentication)
public_urlpatterns = [
    path('public/company-info/<str:tenant_slug>/', get_company_info, name='public_company_info'),
]

