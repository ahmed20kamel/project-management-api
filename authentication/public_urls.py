from django.urls import path
from .public_views import get_company_info

urlpatterns = [
    path('company-info/<str:tenant_slug>/', get_company_info, name='public_company_info'),
]

