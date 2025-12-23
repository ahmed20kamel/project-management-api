# backend/projects/views.py
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import models
from django.conf import settings
import os
from pathlib import Path

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated

from .models import (
    Project, SitePlan, SitePlanOwner, BuildingLicense, Contract, Awarding, Payment,
    Variation, ActualInvoice, Consultant, ProjectConsultant
)
from .serializers import (
    ProjectSerializer,
    SitePlanSerializer,
    BuildingLicenseSerializer,
    ContractSerializer,
    AwardingSerializer,
    PaymentSerializer,
    VariationSerializer,
    ActualInvoiceSerializer,
    ConsultantSerializer,
    ProjectConsultantSerializer,
)
from decimal import Decimal
from datetime import datetime
from authentication.utils import (
    requires_approval, create_pending_change, can_access_financial_data,
    can_manage_contracts, can_manage_payments, is_company_admin, is_staff_user,
    log_audit, get_client_ip
)


# ===============================
# CSRF Cookie
# ===============================
@ensure_csrf_cookie
def csrf_ping(request):
    """زرع كوكي CSRF عند أول GET (للفرونت)"""
    return JsonResponse({"ok": True})


# ===============================
# المشاريع
# ===============================
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by("-created_at")
    serializer_class = ProjectSerializer
    
    def get_queryset(self):
        """تصفية المشاريع حسب tenant المستخدم"""
        queryset = super().get_queryset()
        
        # إذا كان المستخدم superuser، يمكنه رؤية جميع المشاريع
        if self.request.user.is_superuser:
            return queryset
        
        # تصفية حسب tenant المستخدم
        if hasattr(self.request, 'tenant') and self.request.tenant:
            queryset = queryset.filter(tenant=self.request.tenant)
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        else:
            # إذا لم يكن للمستخدم tenant، لا يعرض أي مشاريع
            queryset = queryset.none()
        
        return queryset
    
    def perform_create(self, serializer):
        """ربط المشروع الجديد بـ tenant المستخدم والتحقق من Limits"""
        from authentication.models import TenantSettings
        from rest_framework import serializers as drf_serializers
        
        tenant = None
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            tenant = self.request.user.tenant
        
        # التحقق من Limits (فقط للمستخدمين التابعين لشركة)
        if tenant and not self.request.user.is_superuser:
            try:
                settings = tenant.settings
                # حساب عدد المشاريع الحالية
                current_projects_count = Project.objects.filter(tenant=tenant).count()
                
                # التحقق من الحد الأقصى
                if current_projects_count >= settings.max_projects:
                    raise drf_serializers.ValidationError({
                        'error': f'تم الوصول للحد الأقصى لعدد المشاريع ({settings.max_projects}). يرجى التواصل مع مدير النظام لزيادة الحد.'
                    })
                
                # التحقق من حالة الاشتراك
                if settings.subscription_status in ['suspended', 'expired']:
                    raise drf_serializers.ValidationError({
                        'error': f'لا يمكن إنشاء مشاريع جديدة. حالة الاشتراك: {settings.get_subscription_status_display()}'
                    })
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نسمح بإنشاء المشروع
        
        # التحقق من الصلاحيات: Staff User يحتاج موافقة
        if requires_approval(self.request.user, 'Project'):
            # إنشاء Pending Change بدلاً من إنشاء المشروع مباشرة
            data = serializer.validated_data
            pending_change = create_pending_change(
                user=self.request.user,
                action='create',
                model_name='Project',
                object_id='new',  # سيتم تحديثه بعد الموافقة
                data=data,
                tenant=tenant
            )
            # تسجيل Audit Log
            log_audit(
                user=self.request.user,
                action='create',
                model_name='Project',
                description=f'Created project pending approval (ID: {pending_change.id})',
                ip_address=get_client_ip(self.request)
            )
            # إرجاع رسالة للمستخدم
            raise drf_serializers.ValidationError({
                'message': 'تم إرسال طلب إنشاء المشروع للموافقة',
                'pending_change_id': pending_change.id,
                'requires_approval': True
            })
        
        # ربط المشروع بـ tenant
        if tenant:
            serializer.save(tenant=tenant)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """إرسال المشروع للموافقة"""
        from authentication.utils import check_workflow_permission, log_audit, get_client_ip
        from django.utils import timezone
        
        project = self.get_object()
        user = request.user
        
        if not project.current_stage:
            return Response(
                {'error': 'Project has no current stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من الصلاحية
        if not check_workflow_permission(user, project.current_stage, 'submit'):
            return Response(
                {'error': 'Permission denied: You do not have permission to submit'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # تحديث حالة الموافقة
        project.approval_status = 'pending'
        project.save(update_fields=['approval_status'])
        
        # تسجيل العملية
        log_audit(
            user=user,
            action='submit',
            model_name='Project',
            object_id=project.id,
            description=f'Submitted project for approval',
            ip_address=get_client_ip(request),
            stage=project.current_stage
        )
        
        return Response({
            'message': 'Project submitted successfully',
            'approval_status': project.approval_status
        })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """الموافقة على المشروع"""
        from authentication.utils import check_workflow_permission, log_audit, get_client_ip
        from django.utils import timezone
        
        project = self.get_object()
        user = request.user
        notes = request.data.get('notes', '')
        
        if not project.current_stage:
            return Response(
                {'error': 'Project has no current stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من الصلاحية
        if not check_workflow_permission(user, project.current_stage, 'approve'):
            return Response(
                {'error': 'Permission denied: You do not have permission to approve'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # تحديث حالة الموافقة
        project.approval_status = 'approved'
        project.last_approved_by = user
        project.last_approved_at = timezone.now()
        project.approval_notes = notes
        project.save(update_fields=['approval_status', 'last_approved_by', 'last_approved_at', 'approval_notes'])
        
        # تسجيل العملية
        log_audit(
            user=user,
            action='approve',
            model_name='Project',
            object_id=project.id,
            description=f'Approved project',
            changes={'before': {'approval_status': 'pending'}, 'after': {'approval_status': 'approved'}},
            ip_address=get_client_ip(request),
            stage=project.current_stage
        )
        
        return Response({
            'message': 'Project approved successfully',
            'approval_status': project.approval_status
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """رفض المشروع"""
        from authentication.utils import check_workflow_permission, log_audit, get_client_ip
        from django.utils import timezone
        
        project = self.get_object()
        user = request.user
        notes = request.data.get('notes', '')
        
        if not notes:
            return Response(
                {'error': 'Rejection notes are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not project.current_stage:
            return Response(
                {'error': 'Project has no current stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من الصلاحية
        if not check_workflow_permission(user, project.current_stage, 'reject'):
            return Response(
                {'error': 'Permission denied: You do not have permission to reject'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # تحديث حالة الموافقة
        project.approval_status = 'rejected'
        project.last_approved_by = user
        project.last_approved_at = timezone.now()
        project.approval_notes = notes
        project.save(update_fields=['approval_status', 'last_approved_by', 'last_approved_at', 'approval_notes'])
        
        # تسجيل العملية
        log_audit(
            user=user,
            action='reject',
            model_name='Project',
            object_id=project.id,
            description=f'Rejected project: {notes}',
            changes={'before': {'approval_status': 'pending'}, 'after': {'approval_status': 'rejected'}},
            ip_address=get_client_ip(request),
            stage=project.current_stage
        )
        
        return Response({
            'message': 'Project rejected',
            'approval_status': project.approval_status
        })
    
    @action(detail=True, methods=['post'])
    def request_delete(self, request, pk=None):
        """طلب حذف المشروع"""
        from authentication.utils import check_workflow_permission, log_audit, get_client_ip
        from django.utils import timezone
        
        project = self.get_object()
        user = request.user
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {'error': 'Delete reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not project.current_stage:
            return Response(
                {'error': 'Project has no current stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من الصلاحية
        if not check_workflow_permission(user, project.current_stage, 'delete_request'):
            return Response(
                {'error': 'Permission denied: You do not have permission to request delete'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # تحديث حالة الموافقة
        project.approval_status = 'delete_requested'
        project.delete_requested_by = user
        project.delete_requested_at = timezone.now()
        project.delete_reason = reason
        project.save(update_fields=['approval_status', 'delete_requested_by', 'delete_requested_at', 'delete_reason'])
        
        # تسجيل العملية
        log_audit(
            user=user,
            action='delete_request',
            model_name='Project',
            object_id=project.id,
            description=f'Requested to delete project: {reason}',
            ip_address=get_client_ip(request),
            stage=project.current_stage
        )
        
        return Response({
            'message': 'Delete request submitted',
            'approval_status': project.approval_status
        })
    
    @action(detail=True, methods=['post'])
    def approve_delete(self, request, pk=None):
        """الموافقة على حذف المشروع"""
        from authentication.utils import check_workflow_permission, log_audit, get_client_ip
        from django.utils import timezone
        
        project = self.get_object()
        user = request.user
        
        if project.approval_status != 'delete_requested':
            return Response(
                {'error': 'Project is not in delete_requested status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not project.current_stage:
            return Response(
                {'error': 'Project has no current stage'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من الصلاحية
        if not check_workflow_permission(user, project.current_stage, 'delete_approve'):
            return Response(
                {'error': 'Permission denied: You do not have permission to approve delete'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # تحديث حالة الموافقة
        project.approval_status = 'delete_approved'
        project.delete_approved_by = user
        project.delete_approved_at = timezone.now()
        project.save(update_fields=['approval_status', 'delete_approved_by', 'delete_approved_at'])
        
        # تسجيل العملية
        log_audit(
            user=user,
            action='delete_approve',
            model_name='Project',
            object_id=project.id,
            description=f'Approved deletion of project',
            ip_address=get_client_ip(request),
            stage=project.current_stage
        )
        
        # حذف المشروع فعلياً
        project_id = project.id
        project.delete()
        
        return Response({
            'message': 'Project deletion approved and project deleted',
            'deleted_project_id': project_id
        })
    
    @action(detail=True, methods=['post'])
    def move_to_stage(self, request, pk=None):
        """نقل المشروع إلى مرحلة جديدة"""
        from authentication.utils import log_audit, get_client_ip
        from authentication.models import WorkflowStage
        from django.utils import timezone
        
        project = self.get_object()
        user = request.user
        stage_code = request.data.get('stage_code')
        
        if not stage_code:
            return Response(
                {'error': 'stage_code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # فقط Staff يمكنهم نقل المشاريع بين المراحل
        if not user.is_staff:
            return Response(
                {'error': 'Permission denied: Only staff can move projects between stages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            new_stage = WorkflowStage.objects.get(code=stage_code, is_active=True)
        except WorkflowStage.DoesNotExist:
            return Response(
                {'error': f'Stage not found: {stage_code}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        old_stage = project.current_stage
        project.current_stage = new_stage
        project.approval_status = 'draft'  # إعادة تعيين حالة الموافقة
        project.save(update_fields=['current_stage', 'approval_status'])
        
        # تسجيل العملية
        log_audit(
            user=user,
            action='edit',
            model_name='Project',
            object_id=project.id,
            description=f'Moved project from {old_stage.code if old_stage else "None"} to {new_stage.code}',
            changes={
                'before': {'stage': old_stage.code if old_stage else None},
                'after': {'stage': new_stage.code}
            },
            ip_address=get_client_ip(request),
            stage=new_stage
        )
        
        return Response({
            'message': f'Project moved to stage {new_stage.name}',
            'current_stage': new_stage.code
        })


# ===============================
# أساس موحّد للـ ViewSets التابعة لمشروع
# ===============================
class _ProjectChildViewSet(viewsets.ModelViewSet):
    """
    أساس موحّد لموارد تابعة لمشروع:
    - يفلتر بالـ project_pk
    - يثبّت الربط في create/update
    - يدعم parsers للملفات و JSON
    """
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def _get_project(self):
        return get_object_or_404(Project, pk=self.kwargs["project_pk"])

    def get_queryset(self):
        """تصفية البيانات حسب tenant المستخدم"""
        queryset = self.queryset
        
        # تصفية حسب tenant
        if not self.request.user.is_superuser:
            if hasattr(self.request, 'tenant') and self.request.tenant:
                queryset = queryset.filter(tenant=self.request.tenant)
            elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                queryset = queryset.filter(tenant=self.request.user.tenant)
            else:
                queryset = queryset.none()
        
        # تصفية حسب project
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            # التحقق من أن المشروع ينتمي لنفس tenant
            try:
                project = Project.objects.get(pk=project_pk)
                if not self.request.user.is_superuser:
                    if hasattr(self.request, 'tenant') and self.request.tenant:
                        if project.tenant != self.request.tenant:
                            return queryset.none()
                    elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                        if project.tenant != self.request.user.tenant:
                            return queryset.none()
                queryset = queryset.filter(project_id=project_pk)
            except Project.DoesNotExist:
                return queryset.none()
        
        return queryset

    def perform_create(self, serializer):
        project = self._get_project()
        # ربط البيانات بـ tenant المشروع
        instance = serializer.save(project=project, tenant=project.tenant)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Created {self.queryset.model.__name__} with ID {instance.id} for project {project.id} and tenant {project.tenant.id if project.tenant else 'None'}")

    def perform_update(self, serializer):
        serializer.save(project=self._get_project())

    def get_serializer_context(self):
        """تمرير request إلى serializer context"""
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


# ===============================
# SitePlan (OneToOne)
# ===============================
class SitePlanViewSet(_ProjectChildViewSet):
    queryset = SitePlan.objects.all().order_by("-created_at")
    serializer_class = SitePlanSerializer

    def create(self, request, *args, **kwargs):
        project = self._get_project()
        if hasattr(project, "siteplan"):
            return Response(
                {"detail": "SitePlan already exists for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """معالجة آمنة لقراءة SitePlan مع التعامل مع الأخطاء"""
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error listing SitePlan for project {kwargs.get('project_pk')}: {e}", exc_info=True)
            # ✅ إرجاع قائمة فارغة بدلاً من 500 error
            return Response([], status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """معالجة آمنة لقراءة SitePlan مع التعامل مع الأخطاء"""
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error retrieving SitePlan {kwargs.get('pk')} for project {kwargs.get('project_pk')}: {e}", exc_info=True)
            # ✅ إرجاع 404 بدلاً من 500 error
            return Response(
                {"detail": "SitePlan not found or error loading data."},
                status=status.HTTP_404_NOT_FOUND
            )


# ===============================
# BuildingLicense (OneToOne + Snapshot من SitePlan)
# ===============================
class BuildingLicenseViewSet(_ProjectChildViewSet):
    queryset = BuildingLicense.objects.all().order_by("-created_at")
    serializer_class = BuildingLicenseSerializer

    def create(self, request, *args, **kwargs):
        project = self._get_project()
        if hasattr(project, "license"):
            return Response(
                {"detail": "BuildingLicense already exists for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)
    
    @action(detail=True, methods=["post"], url_path="restore-owners")
    def restore_owners(self, request, project_pk=None, pk=None):
        """استعادة الملاك من الرخصة إلى Site Plan"""
        license_obj = self.get_object()
        
        try:
            siteplan = license_obj.project.siteplan
        except SitePlan.DoesNotExist:
            return Response(
                {"detail": "SitePlan does not exist for this project."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # ✅ الحصول على الملاك من الرخصة
        owners_data = license_obj.owners
        if not owners_data or not isinstance(owners_data, list) or len(owners_data) == 0:
            return Response(
                {"detail": "No owners found in license."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # ✅ حذف الملاك الموجودين في Site Plan
        siteplan.owners.all().delete()
        
        # ✅ استعادة الملاك من الرخصة
        restored_count = 0
        for owner_data in owners_data:
            # ✅ تحويل التواريخ
            id_issue_date = None
            id_expiry_date = None
            if owner_data.get("id_issue_date"):
                try:
                    if isinstance(owner_data["id_issue_date"], str):
                        id_issue_date = datetime.fromisoformat(owner_data["id_issue_date"].replace('Z', '+00:00')).date()
                    else:
                        id_issue_date = owner_data["id_issue_date"]
                except:
                    pass
            
            if owner_data.get("id_expiry_date"):
                try:
                    if isinstance(owner_data["id_expiry_date"], str):
                        id_expiry_date = datetime.fromisoformat(owner_data["id_expiry_date"].replace('Z', '+00:00')).date()
                    else:
                        id_expiry_date = owner_data["id_expiry_date"]
                except:
                    pass
            
            # ✅ تحويل share_percent
            share_percent = owner_data.get("share_percent", "100.00")
            if isinstance(share_percent, str):
                try:
                    share_percent = Decimal(share_percent)
                except:
                    share_percent = Decimal("100.00")
            elif not isinstance(share_percent, Decimal):
                share_percent = Decimal(str(share_percent))
            
            # ✅ إنشاء المالك
            SitePlanOwner.objects.create(
                siteplan=siteplan,
                owner_name_ar=owner_data.get("owner_name_ar", ""),
                owner_name_en=owner_data.get("owner_name_en", ""),
                nationality=owner_data.get("nationality", ""),
                phone=owner_data.get("phone", ""),
                email=owner_data.get("email", ""),
                id_number=owner_data.get("id_number", ""),
                id_issue_date=id_issue_date,
                id_expiry_date=id_expiry_date,
                right_hold_type=owner_data.get("right_hold_type", "Ownership"),
                share_possession=owner_data.get("share_possession", ""),
                share_percent=share_percent,
            )
            restored_count += 1
        
        # ✅ تحديث اسم المشروع
        siteplan.refresh_from_db()
        serializer_instance = SitePlanSerializer()
        serializer_instance._update_project_name_from_owners(siteplan)
        
        # ✅ تحديث snapshot في الرخصة
        from .serializers import build_siteplan_snapshot
        license_obj.siteplan_snapshot = build_siteplan_snapshot(siteplan)
        license_obj.save(update_fields=["siteplan_snapshot"])
        
        return Response({
            "detail": f"Successfully restored {restored_count} owners to Site Plan.",
            "restored_count": restored_count
        })


# ===============================
# Contract (OneToOne + Snapshot من License)
# ===============================
class ContractViewSet(_ProjectChildViewSet):
    queryset = Contract.objects.all().order_by("-created_at")
    serializer_class = ContractSerializer

    def create(self, request, *args, **kwargs):
        # التحقق من الصلاحيات: Staff User لا يمكنه إنشاء عقود
        if not can_manage_contracts(request.user):
            return Response(
                {"error": "You do not have permission to create contracts. Only company admin can manage contracts."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        project = self._get_project()
        if hasattr(project, "contract"):
            return Response(
                {"detail": "Contract already exists for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)
    
    def perform_update(self, serializer):
        # التحقق من الصلاحيات: Staff User لا يمكنه تعديل عقود
        if not can_manage_contracts(self.request.user):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'error': 'You do not have permission to update contracts. Only company admin can manage contracts.'
            })
        serializer.save(project=self._get_project())
    
    def perform_destroy(self, instance):
        # التحقق من الصلاحيات: Staff User لا يمكنه حذف عقود
        if not can_manage_contracts(self.request.user):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'error': 'You do not have permission to delete contracts. Only company admin can manage contracts.'
            })
        instance.delete()


# ===============================
# Awarding (OneToOne)
# ===============================
class AwardingViewSet(_ProjectChildViewSet):
    queryset = Awarding.objects.all().order_by("-created_at")
    serializer_class = AwardingSerializer

    def create(self, request, *args, **kwargs):
        project = self._get_project()
        if hasattr(project, "awarding"):
            return Response(
                {"detail": "Awarding already exists for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)


# ===============================
# Payment (ManyToOne - يمكن أن يكون بدون مشروع)
# ===============================
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().order_by("-date", "-created_at")
    serializer_class = PaymentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        try:
            queryset = Payment.objects.all().order_by("-date", "-created_at")
            
            # تصفية حسب tenant
            if not self.request.user.is_superuser:
                if hasattr(self.request, 'tenant') and self.request.tenant:
                    queryset = queryset.filter(tenant=self.request.tenant)
                elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                    queryset = queryset.filter(tenant=self.request.user.tenant)
                else:
                    queryset = queryset.none()
            
            project_pk = self.kwargs.get("project_pk")
            if project_pk:
                queryset = queryset.filter(project_id=project_pk)
            return queryset
        except Exception as e:
            # ✅ إذا كان الجدول غير موجود، نرجع queryset فارغ
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting payments queryset: {e}")
            return Payment.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error listing payments: {e}")
            # ✅ إرجاع قائمة فارغة بدلاً من 500 error
            return Response([], status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        # التحقق من الصلاحيات: Staff User لا يمكنه إنشاء دفعات
        if not can_manage_payments(self.request.user):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'error': 'You do not have permission to create payments. Only company admin can manage payments.'
            })
        
        # ربط الدفعة بـ tenant
        tenant = None
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            tenant = self.request.user.tenant
        
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            payment = serializer.save(project=project, tenant=tenant if tenant else project.tenant)
        else:
            payment = serializer.save(tenant=tenant)
        
        # ✅ ربط Payment بفاتورة فعلية موجودة أو إنشاء واحدة جديدة
        if payment.payer == 'owner' and payment.project:
            try:
                # Get actual_invoice_id from request data if provided
                actual_invoice_id = None
                if hasattr(self.request, 'data'):
                    request_data = self.request.data
                    if isinstance(request_data, dict):
                        actual_invoice_id = request_data.get('actual_invoice')
                    elif hasattr(request_data, 'get'):
                        actual_invoice_id = request_data.get('actual_invoice')
                
                # ✅ إذا تم تحديد فاتورة فعلية موجودة، ربطها بالدفعة
                if actual_invoice_id:
                    try:
                        actual_invoice = ActualInvoice.objects.get(
                            id=int(actual_invoice_id),
                            project=payment.project,
                            payment__isnull=True  # ✅ فقط الفواتير غير المرتبطة بدفعة
                        )
                        # ✅ ربط الفاتورة الفعلية بالدفعة
                        actual_invoice.payment = payment
                        actual_invoice.save(update_fields=['payment'])
                    except (ActualInvoice.DoesNotExist, ValueError):
                        from rest_framework import serializers as drf_serializers
                        raise drf_serializers.ValidationError({
                            'actual_invoice': f'Actual Invoice {actual_invoice_id} not found or already linked to another payment.'
                        })
                else:
                    # إنشاء فاتورة جديدة مرتبطة بالدفعة
                    if payment.project:
                        actual_invoice = ActualInvoice.objects.create(
                            project=payment.project,
                            payment=payment,
                            amount=payment.amount,
                            invoice_date=payment.date,
                            description=payment.description or f"Payment invoice for {payment.amount}",
                            tenant=payment.tenant
                        )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error linking/creating ActualInvoice for payment {payment.id}: {e}")
                # Re-raise validation errors
                from rest_framework import serializers as drf_serializers
                if isinstance(e, drf_serializers.ValidationError):
                    raise
        
        # ✅ تحديث حالة المشروع تلقائياً بعد إضافة الدفعة (سيتم عبر signal)

    def perform_update(self, serializer):
        # التحقق من الصلاحيات: Staff User لا يمكنه تعديل دفعات
        if not can_manage_payments(self.request.user):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'error': 'You do not have permission to update payments. Only company admin can manage payments.'
            })
        payment = serializer.save()
        # ✅ تحديث حالة المشروع تلقائياً بعد تعديل الدفعة (سيتم عبر signal)
    
    def perform_destroy(self, instance):
        # التحقق من الصلاحيات: Staff User لا يمكنه حذف دفعات
        if not can_manage_payments(self.request.user):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'error': 'You do not have permission to delete payments. Only company admin can manage payments.'
            })
        project_id = instance.project_id if instance.project else None
        instance.delete()
        # ✅ تحديث حالة المشروع تلقائياً بعد حذف الدفعة (سيتم عبر signal)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


# =========================
# Variation ViewSet
# =========================
class VariationViewSet(_ProjectChildViewSet):
    queryset = Variation.objects.all().order_by("-approval_date", "-created_at")
    serializer_class = VariationSerializer

    def perform_create(self, serializer):
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            variation = serializer.save(project=project, tenant=project.tenant)
            # Recalculate project values after variation is added
            _recalculate_project_after_variation(project, variation)
        else:
            variation = serializer.save()
            if variation.project:
                _recalculate_project_after_variation(variation.project, variation)

    def perform_update(self, serializer):
        old_net_with_vat = serializer.instance.net_amount_with_vat if serializer.instance else None
        variation = serializer.save()
        if variation.project:
            # Always recalculate when variation is updated
            _recalculate_project_after_variation(variation.project, variation)

    def perform_destroy(self, instance):
        project = instance.project
        net_with_vat = instance.net_amount_with_vat or Decimal('0')
        instance.delete()
        # Recalculate project values after variation is removed
        if project:
            _recalculate_project_after_variation_removal(project, net_with_vat)


# =========================
# Invoice ViewSet
# =========================
class ActualInvoiceViewSet(_ProjectChildViewSet):
    queryset = ActualInvoice.objects.all().order_by("-invoice_date", "-created_at")
    serializer_class = ActualInvoiceSerializer
    
    def list(self, request, *args, **kwargs):
        """Handle potential database errors gracefully"""
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error listing actual invoices: {e}", exc_info=True)
            # ✅ Return empty list instead of 500 error if items field doesn't exist
            return Response([], status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        """Handle potential database errors gracefully"""
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error retrieving actual invoice: {e}", exc_info=True)
            return Response(
                {"detail": "Error retrieving invoice. Please check database schema."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =========================
# Helper Functions for Recalculation
# =========================
def _recalculate_project_after_variation(project, variation):
    """Recalculate project values after adding/updating a variation"""
    try:
        from decimal import Decimal
        
        # Get contract
        try:
            contract = project.contract
        except Contract.DoesNotExist:
            return
        
        # Calculate total variations for this project using net_amount_with_vat (المبلغ الصافي بالضريبة)
        total_variations = Variation.objects.filter(project=project).aggregate(
            total=models.Sum('net_amount_with_vat')
        )['total'] or Decimal('0')
        
        # Get original value (before any variations)
        # We need to subtract old variations to get the base value
        try:
            # Try to get the original value from contract (before variations)
            # If not available, we'll need to calculate it differently
            original_value = contract.total_project_value or Decimal('0')
            # Subtract all current variations to get base value
            current_variations_sum = Variation.objects.filter(project=project).exclude(id=variation.id).aggregate(
                total=models.Sum('net_amount_with_vat')
            )['total'] or Decimal('0')
            base_value = original_value - current_variations_sum
        except:
            # Fallback: use contract's original value if available
            base_value = contract.total_project_value or Decimal('0')
        
        # Update total_project_value (base + all variations with VAT)
        contract.total_project_value = base_value + total_variations
        
        # Recalculate owner share if it's calculated
        if contract.contract_classification == "housing_loan_program":
            # Owner share = total - bank value
            bank_value = contract.total_bank_value or Decimal('0')
            contract.total_owner_value = contract.total_project_value - bank_value
        else:
            # For private funding, owner value = total
            contract.total_owner_value = contract.total_project_value
        
        contract.save(update_fields=['total_project_value', 'total_owner_value'])
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error recalculating project after variation: {e}")


def _recalculate_project_after_variation_removal(project, removed_net_with_vat):
    """Recalculate project values after removing a variation"""
    try:
        from decimal import Decimal
        
        # Get contract
        try:
            contract = project.contract
        except Contract.DoesNotExist:
            return
        
        # Calculate total variations for this project (excluding the removed one)
        total_variations = Variation.objects.filter(project=project).aggregate(
            total=models.Sum('net_amount_with_vat')
        )['total'] or Decimal('0')
        
        # Update total_project_value
        # Subtract the removed variation's net_amount_with_vat from current total
        current_total = contract.total_project_value or Decimal('0')
        contract.total_project_value = current_total - removed_net_with_vat + total_variations
        
        # Recalculate owner share
        if contract.contract_classification == "housing_loan_program":
            bank_value = contract.total_bank_value or Decimal('0')
            contract.total_owner_value = contract.total_project_value - bank_value
        else:
            contract.total_owner_value = contract.total_project_value
        
        contract.save(update_fields=['total_project_value', 'total_owner_value'])
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error recalculating project after variation removal: {e}")


# ===============================
# File Download Endpoint (Protected)
# ===============================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_file(request, file_path):
    """
    Endpoint محمي لتحميل الملفات مع authentication
    يستقبل مسار الملف النسبي (مثل: contracts/main/file.pdf)
    ويرجع الملف مع authentication
    """
    try:
        # ✅ تنظيف المسار لمنع directory traversal attacks
        # إزالة أي محاولة للوصول إلى ملفات خارج media/
        file_path = file_path.lstrip('/')
        
        # ✅ فك ترميز URL (للتعامل مع الأحرف العربية)
        import urllib.parse
        try:
            file_path = urllib.parse.unquote(file_path)
        except:
            pass  # إذا فشل فك الترميز، نستخدم المسار كما هو
        
        if '..' in file_path or file_path.startswith('/'):
            return Response(
                {"detail": "Invalid file path"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ بناء المسار الكامل للملف
        media_root = Path(settings.MEDIA_ROOT)
        full_path = media_root / file_path
        
        # ✅ التأكد من أن الملف موجود
        if not full_path.exists() or not full_path.is_file():
            return Response(
                {"detail": "File not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ✅ التأكد من أن الملف داخل MEDIA_ROOT (منع directory traversal)
        try:
            full_path.resolve().relative_to(media_root.resolve())
        except ValueError:
            return Response(
                {"detail": "Invalid file path"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ تحديد content type
        import mimetypes
        content_type, encoding = mimetypes.guess_type(str(full_path))
        if not content_type:
            content_type = 'application/octet-stream'
        
        # ✅ إرجاع الملف مع headers مناسبة
        response = FileResponse(
            open(full_path, 'rb'),
            content_type=content_type
        )
        
        # ✅ إضافة Content-Disposition header
        filename = os.path.basename(file_path)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        # ✅ إضافة CORS headers إذا لزم الأمر
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        
        return response
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error downloading file {file_path}: {e}", exc_info=True)
        return Response(
            {"detail": "Error downloading file"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===============================
# الاستشاريون
# ===============================
class ConsultantViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة الاستشاريين"""
    queryset = Consultant.objects.all().order_by("name")
    serializer_class = ConsultantSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """تصفية الاستشاريين حسب tenant المستخدم"""
        queryset = super().get_queryset()
        
        # إذا كان المستخدم superuser، يمكنه رؤية جميع الاستشاريين
        if self.request.user.is_superuser:
            return queryset
        
        # تصفية حسب tenant المستخدم
        tenant = None
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            tenant = self.request.user.tenant
        
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        else:
            queryset = queryset.none()
        
        # فلترة حسب البحث
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(name_en__icontains=search) |
                models.Q(license_no__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """ربط الاستشاري الجديد بـ tenant المستخدم"""
        tenant = None
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            tenant = self.request.user.tenant
        
        if not tenant:
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({
                'tenant': 'User must be associated with a tenant'
            })
        
        serializer.save(tenant=tenant)
    
    @action(detail=True, methods=['get'])
    def projects(self, request, pk=None):
        """الحصول على قائمة المشاريع المرتبطة بالاستشاري"""
        consultant = self.get_object()
        project_consultants = ProjectConsultant.objects.filter(consultant=consultant)
        
        projects_data = []
        for pc in project_consultants:
            projects_data.append({
                "project_id": pc.project.id,
                "project_name": pc.project.name or f"Project #{pc.project.id}",
                "role": pc.role,
                "role_display": dict(ProjectConsultant.ROLE_CHOICES).get(pc.role, pc.role),
            })
        
        return Response(projects_data)


class ProjectConsultantViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة ربط الاستشاريين بالمشاريع"""
    queryset = ProjectConsultant.objects.all()
    serializer_class = ProjectConsultantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """تصفية حسب tenant المستخدم"""
        queryset = super().get_queryset()
        
        if self.request.user.is_superuser:
            return queryset
        
        tenant = None
        if hasattr(self.request, 'tenant') and self.request.tenant:
            tenant = self.request.tenant
        elif hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            tenant = self.request.user.tenant
        
        if tenant:
            queryset = queryset.filter(
                models.Q(project__tenant=tenant) | models.Q(consultant__tenant=tenant)
            )
        else:
            queryset = queryset.none()
        
        # فلترة حسب المشروع
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        # فلترة حسب الاستشاري
        consultant_id = self.request.query_params.get('consultant', None)
        if consultant_id:
            queryset = queryset.filter(consultant_id=consultant_id)
        
        return queryset
