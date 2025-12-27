# backend/projects/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet,
    SitePlanViewSet,
    BuildingLicenseViewSet,
    ContractViewSet,
    AwardingViewSet,
    StartOrderViewSet,
    PaymentViewSet,
    VariationViewSet,
    ActualInvoiceViewSet,
    ConsultantViewSet,
    ProjectConsultantViewSet,
    download_file,
)

# استخدام Router للمشاريع لتفعيل الـ @action decorators
router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

# SitePlan
siteplan_list = SitePlanViewSet.as_view({"get": "list", "post": "create"})
siteplan_detail = SitePlanViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Building License
license_list = BuildingLicenseViewSet.as_view({"get": "list", "post": "create"})
license_detail = BuildingLicenseViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Contract ⬇️
contract_list = ContractViewSet.as_view({"get": "list", "post": "create"})
contract_detail = ContractViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Awarding ⬇️
awarding_list = AwardingViewSet.as_view({"get": "list", "post": "create"})
awarding_detail = AwardingViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# StartOrder ⬇️
startorder_list = StartOrderViewSet.as_view({"get": "list", "post": "create"})
startorder_detail = StartOrderViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Payment ⬇️
payment_list = PaymentViewSet.as_view({"get": "list", "post": "create"})
payment_detail = PaymentViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Variation ⬇️
variation_list = VariationViewSet.as_view({"get": "list", "post": "create"})
variation_detail = VariationViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Invoice ⬇️
actual_invoice_list = ActualInvoiceViewSet.as_view({"get": "list", "post": "create"})
actual_invoice_detail = ActualInvoiceViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

# Consultant ⬇️
consultant_list = ConsultantViewSet.as_view({"get": "list", "post": "create"})
consultant_detail = ConsultantViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
consultant_projects = ConsultantViewSet.as_view({"get": "projects"})

# ProjectConsultant ⬇️
project_consultant_list = ProjectConsultantViewSet.as_view({"get": "list", "post": "create"})
project_consultant_detail = ProjectConsultantViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    # استخدام router للمشاريع (يتضمن كل الـ actions تلقائياً)
    path("", include(router.urls)),

    path("projects/<int:project_pk>/siteplan/", siteplan_list, name="siteplan-list"),
    path("projects/<int:project_pk>/siteplan/<int:pk>/", siteplan_detail, name="siteplan-detail"),

    path("projects/<int:project_pk>/license/", license_list, name="license-list"),
    path("projects/<int:project_pk>/license/<int:pk>/", license_detail, name="license-detail"),

    # ✅ Contract endpoints المطلوبة للفرونت
    path("projects/<int:project_pk>/contract/", contract_list, name="contract-list"),
    path("projects/<int:project_pk>/contract/<int:pk>/", contract_detail, name="contract-detail"),
    
    # ✅ Awarding endpoints
    path("projects/<int:project_pk>/awarding/", awarding_list, name="awarding-list"),
    path("projects/<int:project_pk>/awarding/<int:pk>/", awarding_detail, name="awarding-detail"),
    
    # ✅ StartOrder endpoints
    path("projects/<int:project_pk>/start-order/", startorder_list, name="startorder-list"),
    path("projects/<int:project_pk>/start-order/<int:pk>/", startorder_detail, name="startorder-detail"),
    
    # ✅ Payment endpoints
    path("payments/", payment_list, name="payment-list"),
    path("payments/<int:pk>/", payment_detail, name="payment-detail"),
    path("projects/<int:project_pk>/payments/", payment_list, name="project-payment-list"),
    path("projects/<int:project_pk>/payments/<int:pk>/", payment_detail, name="project-payment-detail"),
    
    # ✅ Variation endpoints
    path("projects/<int:project_pk>/variations/", variation_list, name="variation-list"),
    path("projects/<int:project_pk>/variations/<int:pk>/", variation_detail, name="variation-detail"),
    
    # ✅ Invoice endpoints
    path("projects/<int:project_pk>/actual-invoices/", actual_invoice_list, name="actual-invoice-list"),
    path("projects/<int:project_pk>/actual-invoices/<int:pk>/", actual_invoice_detail, name="actual-invoice-detail"),
    
    # ✅ Protected File Download endpoint
    path("files/<path:file_path>", download_file, name="download-file"),
    
    # ✅ Consultant endpoints
    path("consultants/", consultant_list, name="consultant-list"),
    path("consultants/<int:pk>/", consultant_detail, name="consultant-detail"),
    path("consultants/<int:pk>/projects/", consultant_projects, name="consultant-projects"),
    
    # ✅ ProjectConsultant endpoints
    path("project-consultants/", project_consultant_list, name="project-consultant-list"),
    path("project-consultants/<int:pk>/", project_consultant_detail, name="project-consultant-detail"),
]
