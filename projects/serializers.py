import re
import json
from django.db import models
from rest_framework import serializers
from .models import (
    Project, SitePlan, SitePlanOwner, BuildingLicense, Contract, Awarding, Payment,
    Variation, ActualInvoice, Consultant, ProjectConsultant
)

# Import WorkflowStage for serializer
try:
    from authentication.models import WorkflowStage
except ImportError:
    WorkflowStage = None

# =========================
# Helpers (snapshots)
# =========================
def build_siteplan_snapshot(sp: SitePlan):
    """إنشاء لقطة ثابتة من الـ SitePlan (بما فيها الملاك والملفات)."""
    owners = []
    try:
        for o in sp.owners.all().order_by("id"):
            try:
                # ✅ معالجة آمنة لـ id_attachment
                id_attachment_url = None
                if hasattr(o, 'id_attachment') and o.id_attachment:
                    try:
                        id_attachment_url = o.id_attachment.url if hasattr(o.id_attachment, 'url') else None
                    except Exception:
                        id_attachment_url = None
                
                owner_data = {
                    "owner_name_ar": getattr(o, 'owner_name_ar', ''),
                    "owner_name_en": getattr(o, 'owner_name_en', ''),
                    "nationality": getattr(o, 'nationality', ''),
                    "phone": getattr(o, 'phone', ''),
                    "email": getattr(o, 'email', ''),
                    "id_number": getattr(o, 'id_number', ''),
                    "id_issue_date": o.id_issue_date.isoformat() if hasattr(o, 'id_issue_date') and o.id_issue_date else None,
                    "id_expiry_date": o.id_expiry_date.isoformat() if hasattr(o, 'id_expiry_date') and o.id_expiry_date else None,
                    "share_possession": getattr(o, 'share_possession', ''),
                    "right_hold_type": getattr(o, 'right_hold_type', 'Ownership'),
                    "share_percent": float(o.share_percent) if hasattr(o, 'share_percent') and o.share_percent is not None else None,
                    "id_attachment": id_attachment_url,
                    "age": getattr(o, 'age', None) if hasattr(o, 'age') else None,  # ✅ العمر المحسوب تلقائياً
                    "is_authorized": getattr(o, 'is_authorized', False) if hasattr(o, 'is_authorized') else False,  # ✅ المالك المفوض
                }
                owners.append(owner_data)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error building snapshot for owner {getattr(o, 'id', 'unknown')}: {e}")
                # ✅ تخطي المالك الذي به خطأ والمتابعة
                continue
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error building owners snapshot for SitePlan {getattr(sp, 'id', 'unknown')}: {e}", exc_info=True)
        owners = []  # ✅ قائمة فارغة في حالة الخطأ
    # ✅ معالجة آمنة لـ application_file
    application_file_url = None
    try:
        if hasattr(sp, 'application_file') and sp.application_file:
            application_file_url = sp.application_file.url if hasattr(sp.application_file, 'url') else None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error accessing application_file for SitePlan {getattr(sp, 'id', 'unknown')}: {e}")
        application_file_url = None
    
    return {
        "property": {
            "municipality": getattr(sp, 'municipality', ''),
            "zone": getattr(sp, 'zone', ''),
            "sector": getattr(sp, 'sector', ''),
            "road_name": getattr(sp, 'road_name', ''),
            "plot_area_sqm": float(sp.plot_area_sqm) if hasattr(sp, 'plot_area_sqm') and sp.plot_area_sqm is not None else None,
            "plot_area_sqft": float(sp.plot_area_sqft) if hasattr(sp, 'plot_area_sqft') and sp.plot_area_sqft is not None else None,
            "land_no": getattr(sp, 'land_no', ''),
            "plot_address": getattr(sp, 'plot_address', ''),
            "construction_status": getattr(sp, 'construction_status', ''),
            "allocation_type": getattr(sp, 'allocation_type', ''),
            "land_use": getattr(sp, 'land_use', ''),
            "base_district": getattr(sp, 'base_district', ''),
            "overlay_district": getattr(sp, 'overlay_district', ''),
            "allocation_date": sp.allocation_date.isoformat() if hasattr(sp, 'allocation_date') and sp.allocation_date else None,
        },
        "developer": {
            "developer_name": getattr(sp, 'developer_name', ''),
            "project_no": getattr(sp, 'project_no', ''),
            "project_name": getattr(sp, 'project_name', ''),
        },
        "application": {
            "application_number": getattr(sp, 'application_number', ''),
            "application_date": sp.application_date.isoformat() if hasattr(sp, 'application_date') and sp.application_date else None,
            "application_file": application_file_url,
        },
        "owners": owners,
        "notes": sp.notes,
    }

def build_license_snapshot(lic: BuildingLicense):
    """إنشاء لقطة ثابتة من الـ License تُحفظ داخل Contract.license_snapshot"""
    try:
        return {
        "license": {
            "license_type": getattr(lic, "license_type", ""),
            "project_no": getattr(lic, "project_no", ""),
            "project_name": getattr(lic, "project_name", ""),
            "license_project_no": getattr(lic, "license_project_no", ""),
            "license_project_name": getattr(lic, "license_project_name", ""),
            "license_no": getattr(lic, "license_no", ""),
            "issue_date": lic.issue_date.isoformat() if getattr(lic, "issue_date", None) else None,
            "last_issue_date": lic.last_issue_date.isoformat() if getattr(lic, "last_issue_date", None) else None,
            "expiry_date": lic.expiry_date.isoformat() if getattr(lic, "expiry_date", None) else None,
            "technical_decision_ref": getattr(lic, "technical_decision_ref", ""),
            "technical_decision_date": lic.technical_decision_date.isoformat() if getattr(lic, "technical_decision_date", None) else None,
            "license_notes": getattr(lic, "license_notes", ""),
            "building_license_file": lic.building_license_file.url if getattr(lic, "building_license_file", None) else None,
        },
        "land": {
            "city": getattr(lic, "city", ""),
            "zone": getattr(lic, "zone", ""),
            "sector": getattr(lic, "sector", ""),
            "plot_no": getattr(lic, "plot_no", ""),
            "plot_address": getattr(lic, "plot_address", ""),
            "plot_area_sqm": float(lic.plot_area_sqm) if getattr(lic, "plot_area_sqm", None) is not None else None,
            "land_use": getattr(lic, "land_use", ""),
            "land_use_sub": getattr(lic, "land_use_sub", ""),
            "land_plan_no": getattr(lic, "land_plan_no", ""),
        },
        "parties": {
            "consultant_same": getattr(lic, "consultant_same", True),
            "design_consultant_name": getattr(lic, "design_consultant_name", ""),
            "design_consultant_license_no": getattr(lic, "design_consultant_license_no", ""),
            "supervision_consultant_name": getattr(lic, "supervision_consultant_name", ""),
            "supervision_consultant_license_no": getattr(lic, "supervision_consultant_license_no", ""),

            "contractor_name": getattr(lic, "contractor_name", ""),
            "contractor_license_no": getattr(lic, "contractor_license_no", ""),
        },

        "siteplan_snapshot": getattr(lic, "siteplan_snapshot", {}) or {},
        "owners": getattr(lic, "owners", []),
    }
    except Exception as e:
        # ✅ في حالة أي خطأ، نرجع snapshot فارغ
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error building license snapshot: {e}", exc_info=True)
        return {}


# =========================
# Project
# =========================
class ProjectSerializer(serializers.ModelSerializer):
    has_siteplan = serializers.ReadOnlyField()
    has_license  = serializers.ReadOnlyField()
    completion   = serializers.ReadOnlyField()

    # الكود الداخلي: M + أرقام، مع شرط أن يكون آخر رقم فردياً (1,3,5,7,9)
    internal_code = serializers.CharField(required=False, allow_blank=True, max_length=40)

    # اسم عرض مشتق من الملاك
    display_name = serializers.SerializerMethodField()
    
    # Workflow fields
    current_stage = serializers.SerializerMethodField()
    current_stage_id = serializers.PrimaryKeyRelatedField(
        queryset=WorkflowStage.objects.filter(is_active=True) if WorkflowStage else None,
        source='current_stage',
        write_only=True,
        required=False,
        allow_null=True
    )
    approval_status = serializers.CharField(read_only=True)
    delete_requested_by = serializers.SerializerMethodField()
    delete_approved_by = serializers.SerializerMethodField()
    last_approved_by = serializers.SerializerMethodField()

    class Meta:
        model  = Project
        fields = [
            "id", "name",
            "display_name",
            "project_type", "villa_category", "contract_type",
            "status", "has_siteplan", "has_license", "completion",
            "internal_code",
            "current_stage", "current_stage_id", "approval_status",
            "delete_requested_by", "delete_requested_at", "delete_reason",
            "delete_approved_by", "delete_approved_at",
            "last_approved_by", "last_approved_at", "approval_notes",
            "created_at", "updated_at",
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تعيين queryset للـ current_stage_id
        if WorkflowStage and 'current_stage_id' in self.fields:
            self.fields['current_stage_id'].queryset = WorkflowStage.objects.filter(is_active=True)
    
    def get_current_stage(self, obj):
        if obj.current_stage:
            return {
                'id': obj.current_stage.id,
                'code': obj.current_stage.code,
                'name': obj.current_stage.name,
                'name_en': obj.current_stage.name_en,
            }
        return None
    
    def get_delete_requested_by(self, obj):
        if obj.delete_requested_by:
            return {
                'id': obj.delete_requested_by.id,
                'email': obj.delete_requested_by.email,
                'full_name': obj.delete_requested_by.get_full_name(),
            }
        return None
    
    def get_delete_approved_by(self, obj):
        if obj.delete_approved_by:
            return {
                'id': obj.delete_approved_by.id,
                'email': obj.delete_approved_by.email,
                'full_name': obj.delete_approved_by.get_full_name(),
            }
        return None
    
    def get_last_approved_by(self, obj):
        if obj.last_approved_by:
            return {
                'id': obj.last_approved_by.id,
                'email': obj.last_approved_by.email,
                'full_name': obj.last_approved_by.get_full_name(),
            }
        return None
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
            "project_type": {"required": False},
            "villa_category": {"required": False},
            "contract_type": {"required": False},
        }

    def validate_internal_code(self, value: str):
        """
        تطبيع الكود الداخلي:
        - يسمح بأي أرقام
        - يضيف حرف M في البداية
        - يشترط أن يكون آخر رقم فردياً (1,3,5,7,9)
        """
        if value in (None, ""):
            return value

        # استخراج الأرقام فقط
        digits = re.sub(r"[^0-9]", "", value or "")
        if not digits:
            raise serializers.ValidationError("Internal code must contain at least one digit.")

        # التحقق من أن آخر رقم فردي
        last = digits[-1]
        if last not in "13579":
            raise serializers.ValidationError("Last digit of internal code must be odd (1,3,5,7,9).")

        normalized = ("M" + digits)[:40]
        return normalized

    def get_display_name(self, obj):
        # نكوّن الاسم من المالك المفوض في الـ SitePlan، ولو أكثر من مالك نضيف "وشركاؤه"
        # ✅ إذا كان obj.name موجوداً، نستخدمه أولاً (هذا هو الاسم المحفوظ من الملاك)
        if obj.name and obj.name.strip():
            return obj.name
        
        # ✅ إذا لم يكن هناك اسم محفوظ، نحاول حسابه من الملاك
        try:
            sp = obj.siteplan
        except SitePlan.DoesNotExist:
            sp = None

        main_name = ""
        owners_count = 0
        if sp:
            qs = sp.owners.all()
            owners_count = qs.count()
            
            # ✅ البحث عن المالك المفوض أولاً
            authorized_owner = qs.filter(is_authorized=True).first()
            
            if authorized_owner:
                ar = (authorized_owner.owner_name_ar or "").strip()
                en = (authorized_owner.owner_name_en or "").strip()
                main_name = ar or en
            else:
                # ✅ إذا لم يكن هناك مالك مفوض محدد، نستخدم الأول (للتوافق مع البيانات القديمة)
                for o in qs.order_by("id"):
                    ar = (o.owner_name_ar or "").strip()
                    en = (o.owner_name_en or "").strip()
                    if ar or en:
                        main_name = ar or en
                        break

        if main_name:
            return f"{main_name} وشركاؤه" if owners_count > 1 else main_name
        
        # ✅ إذا لم يكن هناك اسم ولا ملاك، نستخدم ID أو نص افتراضي
        project_id = getattr(obj, 'id', None)
        if project_id:
            return f"مشروع #{project_id}"
        return "مشروع جديد"

# =========================
# SitePlan + Owners
# =========================
class SitePlanOwnerSerializer(serializers.ModelSerializer):
    id_attachment = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model  = SitePlanOwner
        fields = [
            "id",
            "owner_name_ar", "owner_name_en",
            "nationality", "phone", "email",
            "id_number", "id_issue_date", "id_expiry_date", "id_attachment",
            "right_hold_type", "share_possession", "share_percent",
            "age",  # ✅ العمر المحسوب تلقائياً
            "is_authorized",  # ✅ المالك المفوض
        ]
        read_only_fields = ["age"]  # ✅ العمر محسوب تلقائياً ولا يمكن تعديله مباشرة

    def to_representation(self, instance):
        """معالجة آمنة للبيانات مع التعامل مع الحقول المفقودة"""
        try:
            data = super().to_representation(instance)
            
            # ✅ التأكد من وجود الحقول الجديدة مع قيم افتراضية
            if "age" not in data:
                data["age"] = instance.age if hasattr(instance, 'age') else None
            if "is_authorized" not in data:
                data["is_authorized"] = instance.is_authorized if hasattr(instance, 'is_authorized') else False
            
            # ✅ معالجة آمنة لـ id_attachment
            if "id_attachment" in data and data["id_attachment"]:
                try:
                    # التحقق من أن الملف موجود فعلياً
                    if hasattr(instance, 'id_attachment') and instance.id_attachment:
                        # استخدام URL الملف إذا كان موجوداً
                        data["id_attachment"] = instance.id_attachment.url if hasattr(instance.id_attachment, 'url') else str(instance.id_attachment)
                    else:
                        data["id_attachment"] = None
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error accessing id_attachment for owner {instance.id}: {e}")
                    data["id_attachment"] = None
            
            return data
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in SitePlanOwnerSerializer.to_representation for owner {instance.id}: {e}", exc_info=True)
            # ✅ إرجاع بيانات أساسية في حالة الخطأ
            return {
                "id": instance.id if hasattr(instance, 'id') else None,
                "owner_name_ar": getattr(instance, 'owner_name_ar', ''),
                "owner_name_en": getattr(instance, 'owner_name_en', ''),
                "nationality": getattr(instance, 'nationality', ''),
                "phone": getattr(instance, 'phone', ''),
                "email": getattr(instance, 'email', ''),
                "id_number": getattr(instance, 'id_number', ''),
                "id_issue_date": instance.id_issue_date.isoformat() if hasattr(instance, 'id_issue_date') and instance.id_issue_date else None,
                "id_expiry_date": instance.id_expiry_date.isoformat() if hasattr(instance, 'id_expiry_date') and instance.id_expiry_date else None,
                "id_attachment": None,
                "right_hold_type": getattr(instance, 'right_hold_type', 'Ownership'),
                "share_possession": getattr(instance, 'share_possession', ''),
                "share_percent": str(getattr(instance, 'share_percent', '100')),
                "age": getattr(instance, 'age', None) if hasattr(instance, 'age') else None,
                "is_authorized": getattr(instance, 'is_authorized', False) if hasattr(instance, 'is_authorized') else False,
            }


class SitePlanSerializer(serializers.ModelSerializer):
    owners = SitePlanOwnerSerializer(many=True, read_only=True)
    application_file = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model  = SitePlan
        fields = [
            "id", "project",
            # العقار
            "municipality", "zone", "sector", "road_name",
            "plot_area_sqm", "plot_area_sqft",
            "land_no", "plot_address",
            "construction_status", "allocation_type", "land_use",
            "base_district", "overlay_district",
            "allocation_date",
            # المطور
            "project_no", "project_name", "developer_name",
            # مصدر المشروع
            "source_of_project",
            # ملاحظات
            "notes",
            # المعاملة
            "application_number", "application_date", "application_file",
            # الملاك
            "owners",
            "created_at", "updated_at",
        ]
        read_only_fields = ["project", "created_at", "updated_at"]

    # ----- helpers -----
    _owner_allowed = {
        "id",  # ✅ إضافة id للملاك الموجودين
        "owner_name_ar", "owner_name_en",
        "nationality", "phone", "email",
        "id_number", "id_issue_date", "id_expiry_date", "id_attachment",
        "right_hold_type", "share_possession", "share_percent",
        "age",  # ✅ العمر المحسوب تلقائياً
        "is_authorized",  # ✅ المالك المفوض
    }
    _owners_key_re = re.compile(r"^owners\[(\d+)\]\[(\w+)\]$")

    @staticmethod
    def _normalize_owner(o: dict):
        alias = (o.get("owner_name") or "").strip()
        ar = (o.get("owner_name_ar") or "").strip()
        en = (o.get("owner_name_en") or "").strip()
        if alias and not ar and not en:
            ar = en = alias
        if ar and not en:
            en = ar
        if en and not ar:
            ar = en

        c = {k: o.get(k) for k in SitePlanSerializer._owner_allowed if k in o}
        
        # ✅ تحويل is_authorized إلى boolean
        if "is_authorized" in c:
            is_auth = c["is_authorized"]
            if isinstance(is_auth, str):
                c["is_authorized"] = is_auth.lower() in ("true", "1", "yes")
            elif not isinstance(is_auth, bool):
                c["is_authorized"] = bool(is_auth)
        
        # ✅ الحفاظ على id إذا كان موجوداً (للملاك الموجودين)
        if "id" in o:
            c["id"] = o["id"]
        if ar:
            c["owner_name_ar"] = ar
        if en:
            c["owner_name_en"] = en
        # ✅ التأكد من أن جميع الحقول المهمة موجودة
        for field in ["id_number", "nationality", "phone", "email", "id_issue_date", "id_expiry_date", 
                      "right_hold_type", "share_possession", "share_percent"]:
            if field in o:
                c[field] = o[field]
        if "share_percent" in c and c["share_percent"] in ("", None):
            c["share_percent"] = None
        return c

    @staticmethod
    def _has_name(o: dict) -> bool:
        return bool((o.get("owner_name_ar") or "").strip() or (o.get("owner_name_en") or "").strip())

    def to_representation(self, instance):
        """معالجة آمنة لقراءة SitePlan مع التعامل مع الأخطاء"""
        try:
            data = super().to_representation(instance)
            
            # ✅ معالجة آمنة لـ application_file
            if "application_file" in data and data["application_file"]:
                try:
                    if hasattr(instance, 'application_file') and instance.application_file:
                        # التحقق من أن الملف موجود فعلياً
                        if hasattr(instance.application_file, 'url'):
                            data["application_file"] = instance.application_file.url
                        else:
                            data["application_file"] = str(instance.application_file) if instance.application_file else None
                    else:
                        data["application_file"] = None
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error accessing application_file for SitePlan {instance.id}: {e}")
                    data["application_file"] = None
            
            # ✅ معالجة آمنة للملاك
            if "owners" in data and isinstance(data["owners"], list):
                # البيانات تم معالجتها بالفعل في SitePlanOwnerSerializer.to_representation
                pass
            
            return data
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in SitePlanSerializer.to_representation for SitePlan {instance.id}: {e}", exc_info=True)
            # ✅ إرجاع بيانات أساسية في حالة الخطأ
            try:
                return {
                    "id": instance.id if hasattr(instance, 'id') else None,
                    "project": instance.project_id if hasattr(instance, 'project_id') else None,
                    "municipality": getattr(instance, 'municipality', ''),
                    "zone": getattr(instance, 'zone', ''),
                    "sector": getattr(instance, 'sector', ''),
                    "plot_area_sqm": str(getattr(instance, 'plot_area_sqm', '')) if hasattr(instance, 'plot_area_sqm') else '',
                    "plot_area_sqft": str(getattr(instance, 'plot_area_sqft', '')) if hasattr(instance, 'plot_area_sqft') else '',
                    "land_no": getattr(instance, 'land_no', ''),
                    "allocation_type": getattr(instance, 'allocation_type', ''),
                    "land_use": getattr(instance, 'land_use', ''),
                    "application_number": getattr(instance, 'application_number', ''),
                    "application_date": instance.application_date.isoformat() if hasattr(instance, 'application_date') and instance.application_date else None,
                    "application_file": None,
                    "owners": [],  # ✅ قائمة فارغة بدلاً من خطأ
                    "created_at": instance.created_at.isoformat() if hasattr(instance, 'created_at') and instance.created_at else None,
                    "updated_at": instance.updated_at.isoformat() if hasattr(instance, 'updated_at') and instance.updated_at else None,
                }
            except Exception as inner_e:
                logger.error(f"Error creating fallback representation: {inner_e}", exc_info=True)
                # ✅ إرجاع بيانات فارغة كملاذ أخير
                return {
                    "id": None,
                    "project": None,
                    "owners": [],
                    "application_file": None,
                }

    def _extract_owners_from_request(self):
        """استخراج بيانات الملاك من الطلب (يدعم JSON و multipart)"""
        req = self.context.get("request")
        if not req:
            return None

        data = req.data
        import logging
        logger = logging.getLogger(__name__)
        
        # ✅ Debug: طباعة نوع البيانات
        logger.info(f"Extract owners: req.data type: {type(data)}, has items: {hasattr(data, 'items')}")
        if hasattr(data, 'keys'):
            all_keys = list(data.keys())
            logger.info(f"Extract owners: req.data total keys: {len(all_keys)}")
            # ✅ البحث عن مفاتيح owners
            owner_keys = [k for k in all_keys if 'owner' in k.lower()]
            logger.info(f"Extract owners: owner-related keys: {owner_keys}")
            # ✅ طباعة جميع المفاتيح التي تطابق pattern owners[...]
            matching_keys = [k for k in all_keys if self._owners_key_re.match(str(k))]
            logger.info(f"Extract owners: matching owners pattern keys: {matching_keys}")
            if not matching_keys:
                logger.warning(f"Extract owners: NO keys matching owners pattern!")
                # ✅ طباعة جميع المفاتيح للتحقق
                logger.warning(f"Extract owners: All req.data keys: {all_keys}")
                # ✅ البحث عن أي مفاتيح تحتوي على "owner" (حتى لو لم تطابق الـ pattern)
                any_owner_keys = [k for k in all_keys if 'owner' in str(k).lower()]
                if any_owner_keys:
                    logger.warning(f"Extract owners: Found keys with 'owner' in name: {any_owner_keys}")
        
        # الحصول على الملفات من request.FILES
        try:
            files = req.FILES
        except AttributeError:
            files = getattr(req, '_request', {}).get('FILES', {})
        
        if not files:
            files = {}

        # ✅ محاولة الحصول على req.POST مباشرة (لـ FormData)
        # ✅ في DRF، req._request.POST يحتوي على البيانات من FormData
        post_data = None
        try:
            # ✅ محاولة من req._request.POST (الطلب الأصلي في DRF)
            if hasattr(req, '_request') and hasattr(req._request, 'POST'):
                post_data = req._request.POST
                logger.info(f"Extract owners: req._request.POST available, type: {type(post_data)}")
                if post_data and hasattr(post_data, 'keys'):
                    logger.info(f"Extract owners: req._request.POST keys (first 20): {list(post_data.keys())[:20]}")
            # ✅ محاولة من req.POST (fallback)
            elif hasattr(req, 'POST'):
                post_data = req.POST
                logger.info(f"Extract owners: req.POST available, type: {type(post_data)}")
                if post_data and hasattr(post_data, 'keys'):
                    logger.info(f"Extract owners: req.POST keys (first 20): {list(post_data.keys())[:20]}")
        except Exception as e:
            logger.warning(f"Extract owners: req.POST not available: {e}")
            pass

        # معالجة البيانات النصية
        # ✅ التحقق من وجود "owners" كـ list أو string أولاً
        owners_raw = data.get("owners")
        logger.info(f"Extract owners: owners_raw type: {type(owners_raw)}, value: {owners_raw}")
        
        raw = None  # تهيئة raw
        
        if isinstance(owners_raw, list) and len(owners_raw) > 0:
            raw = owners_raw
            logger.info(f"Extract owners: Found owners as list, count: {len(raw)}")
        elif isinstance(owners_raw, str) and owners_raw.strip():
            # ✅ التحقق من أن الـ string ليس "[object Object]" (خطأ في JavaScript)
            if owners_raw.strip() in ("[object Object]", "[object object]"):
                logger.warning(f"Extract owners: owners is '[object Object]' string (JS error), ignoring and extracting from keys")
                raw = None  # تجاهل هذا القيمة الخاطئة
            else:
                try:
                    parsed = json.loads(owners_raw)
                    raw = parsed if isinstance(parsed, list) and len(parsed) > 0 else None
                    if raw:
                        logger.info(f"Extract owners: Found owners as JSON string, parsed count: {len(raw)}")
                    else:
                        logger.warning(f"Extract owners: Parsed owners is empty, trying to extract from keys")
                except Exception as e:
                    logger.warning(f"Extract owners: Failed to parse owners JSON string: {e}, trying to extract from keys")
                    raw = None  # تجاهل هذا القيمة الخاطئة
        
        # ✅ إذا لم يكن owners موجوداً كـ list أو string صالح، نحاول استخراجه من المفاتيح
        if raw is None:
            buckets = {}
            logger.info(f"Extract owners: owners not found as valid list/string, trying to extract from keys (owners[0][...])")
            
            # ✅ أولاً: محاولة استخراج من req._request.POST مباشرة (البيانات النصية من FormData)
            # ✅ في DRF مع MultiPartParser، req._request.POST يحتوي على البيانات النصية من FormData
            # ✅ هذا مهم جداً - عندما يكون هناك ملفات، req.data قد لا يحتوي على البيانات النصية
            if post_data and hasattr(post_data, 'get'):
                try:
                    post_keys = list(post_data.keys()) if hasattr(post_data, 'keys') else []
                    logger.info(f"Extract owners: Iterating over req._request.POST, total keys: {len(post_keys)}")
                    
                    for k in post_keys:
                        v = post_data.get(k)
                        
                        # ✅ التحقق من الـ pattern
                        k_str = str(k)
                        m = self._owners_key_re.match(k_str)
                        if not m:
                            continue
                        
                        idx = int(m.group(1))
                        key = m.group(2)
                        # ✅ تجاهل id_attachment_url لأنه ليس حقل في النموذج
                        if key == "id_attachment_url":
                            continue
                        
                        logger.info(f"Extract owners: Found owner field in req._request.POST: owners[{idx}][{key}] = {v}")
                        # ✅ معالجة id_attachment_delete كـ boolean
                        if key == "id_attachment_delete":
                            buckets.setdefault(idx, {})[key] = str(v).lower() in ("true", "1", "yes")
                        else:
                            buckets.setdefault(idx, {})[key] = v
                    
                    logger.info(f"Extract owners: After req._request.POST extraction, buckets count: {len(buckets)}")
                except Exception as e:
                    logger.error(f"Error extracting from req._request.POST: {e}", exc_info=True)
            
            # ✅ ثانياً: محاولة استخراج من req.data (fallback إذا لم يكن post_data متاحاً)
            if not buckets and hasattr(data, 'get'):
                try:
                    # ✅ QueryDict في Django - نستخدم .keys() للحصول على جميع المفاتيح
                    data_keys = list(data.keys()) if hasattr(data, 'keys') else []
                    logger.info(f"Extract owners: Fallback - Iterating over req.data, total keys: {len(data_keys)}")
                    
                    for k in data_keys:
                        # ✅ تخطي الملفات - سنتعامل معها من req.FILES
                        v = data.get(k)
                        if hasattr(v, 'read'):  # File object
                            logger.debug(f"Extract owners: Skipping file object: {k}")
                            continue
                        
                        # ✅ التحقق من الـ pattern
                        k_str = str(k)
                        m = self._owners_key_re.match(k_str)
                        if not m:
                            continue
                        
                        idx = int(m.group(1))
                        key = m.group(2)
                        # ✅ تجاهل id_attachment_url لأنه ليس حقل في النموذج
                        if key == "id_attachment_url":
                            continue
                        
                        logger.info(f"Extract owners: Found owner field in req.data: owners[{idx}][{key}] = {v}")
                        # ✅ معالجة id_attachment_delete كـ boolean
                        if key == "id_attachment_delete":
                            buckets.setdefault(idx, {})[key] = str(v).lower() in ("true", "1", "yes")
                        else:
                            buckets.setdefault(idx, {})[key] = v
                    
                    logger.info(f"Extract owners: After req.data extraction, buckets count: {len(buckets)}")
                except Exception as e:
                    logger.error(f"Error extracting from req.data: {e}", exc_info=True)
            
            
            # ✅ دمج الملفات من req.FILES
            if files:
                try:
                    logger.info(f"Extract owners: Processing files from req.FILES, count: {len(files) if hasattr(files, '__len__') else 'unknown'}")
                    for k, v in files.items():
                        k_str = str(k)
                        logger.debug(f"Extract owners: Checking file key: {k_str}")
                        m = self._owners_key_re.match(k_str)
                        if not m:
                            continue
                        idx = int(m.group(1))
                        key = m.group(2)
                        if key == "id_attachment":  # فقط ملفات الهوية
                            logger.info(f"Extract owners: Found id_attachment file for owner {idx}: {k_str}")
                            buckets.setdefault(idx, {})[key] = v
                        else:
                            logger.debug(f"Extract owners: Skipping file key (not id_attachment): {k_str}")
                except (AttributeError, TypeError) as e:
                    logger.error(f"Extract owners: Error processing files: {e}", exc_info=True)
            
            # ✅ إذا كان هناك buckets، نرجع قائمة الملاك
            # إذا لم يكن هناك buckets، نرجع None (يعني لم يتم إرسال owners)
            raw = [buckets[i] for i in sorted(buckets.keys())] if buckets else None
            logger.info(f"Extract owners: buckets count: {len(buckets) if buckets else 0}, raw: {len(raw) if raw else 0}")
            if buckets:
                logger.info(f"Extract owners: buckets content: {buckets}")

        if raw is None:
            logger.warning("Extract owners: raw is None, returning None")
            return None

        # تنظيف وتطبيع البيانات
        cleaned = []
        for idx, o in enumerate(raw):
            if not isinstance(o, dict):
                logger.warning(f"Extract owners: Skipping non-dict at index {idx}: {type(o)}")
                continue
            logger.debug(f"Extract owners: Processing owner {idx}: {o}")
            c = self._normalize_owner(o)
            logger.debug(f"Extract owners: Normalized owner {idx}: {c}")
            has_name = self._has_name(c)
            logger.debug(f"Extract owners: Owner {idx} has_name: {has_name}")
            if has_name:
                cleaned.append(c)
                logger.info(f"Extract owners: Added owner {idx} to cleaned list")
            else:
                logger.warning(f"Extract owners: Skipping owner {idx} without name. Normalized: {c}")
        
        logger.info(f"Extract owners: Final cleaned count: {len(cleaned)}")
        if cleaned:
            logger.info(f"Extract owners: Cleaned owners: {cleaned}")
        return cleaned

    def validate(self, attrs):
        owners_in_attrs = attrs.get("owners", None)
        if isinstance(owners_in_attrs, list):
            normalized = []
            for o in owners_in_attrs:
                c = self._normalize_owner(o or {})
                if self._has_name(c):
                    normalized.append(c)
            attrs["owners"] = normalized
        return attrs

    def _update_project_name_from_owners(self, siteplan: SitePlan):
        """تحديث اسم المشروع بناءً على المالك المفوض"""
        # ✅ إعادة تحميل الملاك من قاعدة البيانات للتأكد من أحدث البيانات
        siteplan.refresh_from_db()
        qs = siteplan.owners.all()
        owners_count = qs.count()
        
        # ✅ البحث عن المالك المفوض أولاً
        authorized_owner = qs.filter(is_authorized=True).first()
        
        if authorized_owner:
            ar = (authorized_owner.owner_name_ar or "").strip()
            en = (authorized_owner.owner_name_en or "").strip()
            main = ar or en
        else:
            # ✅ إذا لم يكن هناك مالك مفوض محدد، نستخدم الأول (للتوافق مع البيانات القديمة)
            main = ""
            for o in qs.order_by("id"):
                ar = (o.owner_name_ar or "").strip()
                en = (o.owner_name_en or "").strip()
                if ar or en:
                    main = ar or en
                    break
        
        if main:
            new_name = f"{main} وشركاؤه" if owners_count > 1 else main
            # ✅ تحديث اسم المشروع فقط إذا كان مختلفاً
            if siteplan.project.name != new_name:
                siteplan.project.name = new_name
                siteplan.project.save(update_fields=["name"])

    def _sync_owners_to_license_and_contract(self, siteplan: SitePlan):
        """تحديث الملاك في الرخصة والعقد تلقائياً عند تحديثها في Site Plan"""
        try:
            project = siteplan.project
            
            # ✅ تحديث الرخصة
            try:
                license_obj = project.license
                # ✅ تحديث siteplan_snapshot
                license_obj.siteplan_snapshot = build_siteplan_snapshot(siteplan)
                
                # ✅ تحديث حقل owners في الرخصة من الملاك الجديدة
                owners_list = []
                for o in siteplan.owners.all().order_by("id"):
                    owners_list.append({
                        "owner_name_ar": o.owner_name_ar,
                        "owner_name_en": o.owner_name_en,
                        "nationality": o.nationality,
                        "phone": o.phone,
                        "email": o.email,
                        "id_number": o.id_number,
                        "id_issue_date": o.id_issue_date.isoformat() if o.id_issue_date else "",
                        "id_expiry_date": o.id_expiry_date.isoformat() if o.id_expiry_date else "",
                        "right_hold_type": o.right_hold_type,
                        "share_possession": o.share_possession,
                        "share_percent": str(o.share_percent) if o.share_percent is not None else "100.00",
                        "age": o.age,  # ✅ العمر المحسوب تلقائياً
                        "is_authorized": o.is_authorized,  # ✅ المالك المفوض
                    })
                
                license_obj.owners = owners_list
                license_obj.save(update_fields=["siteplan_snapshot", "owners"])
            except BuildingLicense.DoesNotExist:
                pass
            
            # ✅ تحديث العقد
            try:
                contract_obj = project.contract
                # ✅ إذا كانت الرخصة موجودة، نحدث license_snapshot في العقد
                try:
                    license_obj = project.license
                    # ✅ إعادة تحميل الرخصة للتأكد من أحدث البيانات (بما فيها owners المحدثة)
                    license_obj.refresh_from_db()
                    contract_obj.license_snapshot = build_license_snapshot(license_obj)
                    contract_obj.save(update_fields=["license_snapshot"])
                except BuildingLicense.DoesNotExist:
                    pass
            except Contract.DoesNotExist:
                pass
                
        except Exception as e:
            # ✅ في حالة الخطأ، نكمل العملية (لا نوقف تحديث Site Plan)
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error syncing owners to license and contract: {e}")

    def create(self, validated_data):
        owners_data = validated_data.pop("owners", None)
        if owners_data is None:
            owners_data = self._extract_owners_from_request() or []

        owners_data = [od for od in owners_data if self._has_name(od)]

        siteplan = SitePlan.objects.create(**validated_data)
        
        # ✅ حفظ الملاك بشكل صحيح
        for idx, od in enumerate(owners_data):
            # ✅ استخراج id_attachment من od
            file_obj = od.pop("id_attachment", None)
            owner = SitePlanOwner.objects.create(siteplan=siteplan, **od)
            
            # ✅ إضافة الملف إذا كان موجوداً مع تعيين الفهرس للدالة upload_to
            if file_obj:
                owner._owner_index = idx + 1
                # حذف أي ملف سابق بنفس المسار لتفادي إضافة لاحقة
                if owner.id_attachment:
                    try:
                        owner.id_attachment.delete(save=False)
                    except Exception:
                        pass
                owner.id_attachment = file_obj
                owner.save()

        # ✅ تحديث اسم المشروع بعد إنشاء الملاك
        siteplan.refresh_from_db()
        self._update_project_name_from_owners(siteplan)
        
        # ✅ تحديث الملاك في الرخصة والعقد تلقائياً (إذا كانت موجودة)
        self._sync_owners_to_license_and_contract(siteplan)
        
        return siteplan


    def update(self, instance, validated_data):
        from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
        import logging
        logger = logging.getLogger(__name__)

        # -----------------------------
        # 1) سحب الملاك من validated_data (يمنع owners = ...)
        # -----------------------------
        owners_data = validated_data.pop("owners", None)
        logger.info(f"Update: owners_data from validated_data: {owners_data is not None}")
        
        # ✅ دائماً نحاول استخراج الملاك من الطلب (لأن FormData لا يمر عبر validated_data)
        extracted_owners = self._extract_owners_from_request()
        logger.info(f"Update: extracted_owners from request: {extracted_owners is not None}, count: {len(extracted_owners) if extracted_owners else 0}")
        
        # ✅ نستخدم الملاك المستخرجة من الطلب إذا كانت موجودة
        if extracted_owners is not None:
            owners_data = extracted_owners
            logger.info(f"Update: Using extracted owners, count: {len(owners_data)}")
        elif owners_data is None:
            logger.warning("Update: No owners found in request or validated_data")

        # -----------------------------
        # 2) التعامل مع ملف المعاملة (application_file)
        # -----------------------------
        file_obj = validated_data.get("application_file")
        if file_obj and isinstance(file_obj, (InMemoryUploadedFile, UploadedFile)):
            # حذف الملف السابق لتجنب إضافة لاحقة على الاسم
            if instance.application_file:
                try:
                    instance.application_file.delete(save=False)
                except Exception:
                    pass

        # -----------------------------
        # 3) تحديث حقول الـ SitePlan
        # -----------------------------
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # -----------------------------
        # 4) لو مفيش ملاك في الريكوست → سيب الموجود وتحديث اسم المشروع
        # -----------------------------
        if owners_data is None:
            # ✅ تحديث اسم المشروع من الملاك الموجودين
            self._update_project_name_from_owners(instance)
            return instance

        # -----------------------------
        # 4) تنظيف وتطبيع بيانات الملاك
        # -----------------------------
        owners_data = [self._normalize_owner(od) for od in owners_data if self._has_name(od)]
        
        # ✅ إذا لم يكن هناك ملاك بعد التنظيف، نحذف الملاك الموجودين ونحدث اسم المشروع
        if not owners_data:
            # حذف جميع الملاك الموجودين
            instance.owners.all().delete()
            # تحديث اسم المشروع إلى القيمة الافتراضية
            instance.project.name = ""
            instance.project.save(update_fields=["name"])
            # ✅ تحديث الملاك في الرخصة والعقد (حذف الملاك)
            self._sync_owners_to_license_and_contract(instance)
            return instance

        # -----------------------------
        # 5) استخراج الملاك الموجودين
        # -----------------------------
        existing = {o.id: o for o in instance.owners.all()}
        received_ids = []

        for od in owners_data:
            # ✅ تحويل id إلى integer إذا كان string
            oid_raw = od.get("id")
            oid = None
            if oid_raw is not None:
                try:
                    oid = int(oid_raw) if not isinstance(oid_raw, int) else oid_raw
                except (ValueError, TypeError):
                    oid = None
            
            # ✅ استخراج id_attachment من od (قد يكون File object أو None)
            file_obj = od.pop("id_attachment", None)
            # ✅ إذا كان id_attachment موجوداً في od كـ None صريح (من الفرونت)، نحذف الملف
            delete_file = od.pop("id_attachment_delete", False)

            if oid and oid in existing:
                # ---- تحديث مالك موجود ----
                obj = existing[oid]

                # ✅ تحديث الملف أولاً
                if file_obj and isinstance(file_obj, (InMemoryUploadedFile, UploadedFile)):
                    # ملف جديد - تعيين الفهرس للدالة upload_to وحذف القديم لتجنب لاحقة
                    obj._owner_index = list(existing.keys()).index(oid) + 1
                    if obj.id_attachment:
                        try:
                            obj.id_attachment.delete(save=False)
                        except Exception:
                            pass
                    obj.id_attachment = file_obj
                elif delete_file:
                    # حذف الملف (إذا كان صريحاً)
                    obj.id_attachment = None
                # ✅ إذا لم يكن هناك ملف جديد ولا حذف، نحافظ على الملف الموجود (لا نفعل شيء)

                # ✅ تحديث باقي الحقول
                for k, v in od.items():
                    # ✅ تخطي id لأنه موجود بالفعل
                    if k == "id":
                        continue
                    # ✅ تخطي id_attachment_delete لأنه ليس حقل في النموذج
                    if k == "id_attachment_delete":
                        continue
                    # ✅ تحديث الحقل
                    setattr(obj, k, v)

                # ✅ حفظ التغييرات
                obj.save(update_fields=None)  # حفظ جميع الحقول
                received_ids.append(oid)

            else:
                # ---- مالك جديد ----
                # ✅ إزالة id من od لأن المالك جديد
                od.pop("id", None)
                new_owner = SitePlanOwner.objects.create(siteplan=instance, **od)
                
                # ✅ إضافة الملف إذا كان موجوداً مع تعيين الفهرس للدالة upload_to
                if file_obj and isinstance(file_obj, (InMemoryUploadedFile, UploadedFile)):
                    # حساب الفهرس بناءً على عدد الملاك الموجودين + الملاك الجدد
                    owner_index = len([o for o in existing.values() if o]) + len([o for o in received_ids if o]) + 1
                    new_owner._owner_index = owner_index
                    # حذف أي ملف سابق (احترازي) لتفادي لاحقة
                    if new_owner.id_attachment:
                        try:
                            new_owner.id_attachment.delete(save=False)
                        except Exception:
                            pass
                    new_owner.id_attachment = file_obj
                    new_owner.save()
                
                received_ids.append(new_owner.id)

        # -----------------------------
        # 6) حذف الملاك اللي مش ظهروا في الريكوست
        # -----------------------------
        for oid, obj in existing.items():
            if oid not in received_ids:
                obj.delete()

        # -----------------------------
        # 7) تحديث اسم المشروع بعد حفظ الملاك
        # -----------------------------
        # ✅ إعادة تحميل instance للتأكد من أحدث البيانات
        instance.refresh_from_db()
        self._update_project_name_from_owners(instance)
        
        # -----------------------------
        # 8) تحديث الملاك في الرخصة والعقد تلقائياً
        # -----------------------------
        self._sync_owners_to_license_and_contract(instance)
        
        return instance


# =========================
# Building License
# =========================
class BuildingLicenseSerializer(serializers.ModelSerializer):
    building_license_file = serializers.FileField(required=False, allow_null=True)
    siteplan_snapshot     = serializers.JSONField(read_only=True)
    owners_names = serializers.SerializerMethodField()

    consultant_same = serializers.BooleanField(required=False)
    design_consultant_name = serializers.CharField(required=False, allow_blank=True)
    design_consultant_name_en = serializers.CharField(required=False, allow_blank=True)
    design_consultant_license_no = serializers.CharField(required=False, allow_blank=True)
    supervision_consultant_name = serializers.CharField(required=False, allow_blank=True)
    supervision_consultant_name_en = serializers.CharField(required=False, allow_blank=True)
    supervision_consultant_license_no = serializers.CharField(required=False, allow_blank=True)

    owners = serializers.JSONField(required=False)
    project_name = serializers.CharField(required=False, allow_blank=True)
    license_project_no = serializers.CharField(required=False, allow_blank=True)
    license_project_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model  = BuildingLicense
        fields = [
            "id", "project",

            "license_type",

            # (المطور)
            "project_no", "project_name",

            # (الرخصة)
            "license_project_no", "license_project_name",

            # بيانات الرخصة
            "license_no",
            "issue_date", "last_issue_date", "expiry_date",
            "technical_decision_ref", "technical_decision_date", "license_notes",
            "building_license_file",

            # الأرض
            "city", "zone", "sector", "plot_no", "plot_address",
            "plot_area_sqm", "land_use", "land_use_sub", "land_plan_no",

            # ========= الاستشاري =========
            "consultant_same",
            "design_consultant_name", "design_consultant_name_en", "design_consultant_license_no",
            "supervision_consultant_name", "supervision_consultant_name_en", "supervision_consultant_license_no",

            # ========= المقاول =========
            "contractor_name", "contractor_name_en", "contractor_license_no",
            "contractor_phone", "contractor_email",  # ✅ إضافة الحقول المفقودة

            # الملاك داخل الرخصة
            "owners",

            # snapshot
            "siteplan_snapshot", "owners_names",

            "created_at", "updated_at",
        ]

        read_only_fields = ["project", "siteplan_snapshot", "created_at", "updated_at"]


    def get_owners_names(self, obj):
        snap = obj.siteplan_snapshot or {}
        owners_data = snap.get("owners", [])
        result = []
        for o in owners_data:
            ar = (o.get("owner_name_ar") or "").strip()
            en = (o.get("owner_name_en") or "").strip()
            if ar or en:
                result.append({"ar": ar, "en": en})
        return result

    def to_representation(self, instance):
        """ملء بيانات المقاول من TenantSettings عند القراءة دائماً (Single Source of Truth)"""
        representation = super().to_representation(instance)
        
        # ✅ ملء بيانات المقاول من TenantSettings دائماً (Single Source of Truth)
        project = instance.project
        if project and project.tenant:
            try:
                from authentication.models import TenantSettings
                tenant_settings = TenantSettings.objects.get(tenant=project.tenant)
                
                # ✅ نستخدم بيانات TenantSettings دائماً لضمان التحديث التلقائي
                if tenant_settings.contractor_name:
                    representation['contractor_name'] = tenant_settings.contractor_name
                if tenant_settings.contractor_name_en:
                    representation['contractor_name_en'] = tenant_settings.contractor_name_en
                if tenant_settings.contractor_license_no:
                    representation['contractor_license_no'] = tenant_settings.contractor_license_no
                if tenant_settings.contractor_phone:
                    representation['contractor_phone'] = tenant_settings.contractor_phone
                if tenant_settings.contractor_email:
                    representation['contractor_email'] = tenant_settings.contractor_email
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نكمل بدون ملء البيانات
        
        return representation

    def to_internal_value(self, data):
        """دعم owners كسلسلة JSON في multipart: owners='[{"owner_name_ar":"..."}, ...]'"""
        ret = super().to_internal_value(data)
        owners_raw = self.initial_data.get("owners")
        if isinstance(owners_raw, str):
            try:
                parsed = json.loads(owners_raw)
                if isinstance(parsed, list):
                    ret["owners"] = parsed
            except Exception:
                pass
        return ret

    def validate(self, attrs):
        issue = attrs.get("issue_date") or getattr(self.instance, "issue_date", None)
        last  = attrs.get("last_issue_date") or getattr(self.instance, "last_issue_date", None)
        if issue and last and last < issue:
            raise serializers.ValidationError({"last_issue_date": "يجب أن يكون بعد/يساوي تاريخ الإصدار."})
        return attrs

    def create(self, validated_data):
        # ✅ ملء بيانات المقاول من TenantSettings تلقائياً إذا لم تكن موجودة
        project = validated_data.get('project')
        if project and project.tenant:
            try:
                from authentication.models import TenantSettings
                tenant_settings = TenantSettings.objects.get(tenant=project.tenant)
                # ✅ ملء بيانات المقاول من TenantSettings إذا كانت فارغة
                if not validated_data.get('contractor_name') and tenant_settings.contractor_name:
                    validated_data['contractor_name'] = tenant_settings.contractor_name
                if not validated_data.get('contractor_name_en') and tenant_settings.contractor_name_en:
                    validated_data['contractor_name_en'] = tenant_settings.contractor_name_en
                if not validated_data.get('contractor_license_no') and tenant_settings.contractor_license_no:
                    validated_data['contractor_license_no'] = tenant_settings.contractor_license_no
                if not validated_data.get('contractor_phone') and tenant_settings.contractor_phone:
                    validated_data['contractor_phone'] = tenant_settings.contractor_phone
                if not validated_data.get('contractor_email') and tenant_settings.contractor_email:
                    validated_data['contractor_email'] = tenant_settings.contractor_email
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نكمل بدون ملء البيانات
        
        lic = BuildingLicense.objects.create(**validated_data)
        try:
            sp = lic.project.siteplan
        except SitePlan.DoesNotExist:
            sp = None
        if sp:
            lic.siteplan_snapshot = build_siteplan_snapshot(sp)
            lic.save(update_fields=["siteplan_snapshot"])
        return lic

    def update(self, instance, validated_data):
        # ✅ ملء بيانات المقاول من TenantSettings تلقائياً إذا لم تكن موجودة أو تم تحديثها
        project = instance.project
        if project and project.tenant:
            try:
                from authentication.models import TenantSettings
                tenant_settings = TenantSettings.objects.get(tenant=project.tenant)
                # ✅ ملء بيانات المقاول من TenantSettings إذا كانت فارغة
                # ✅ نستخدم بيانات TenantSettings دائماً لضمان التحديث التلقائي
                if tenant_settings.contractor_name:
                    validated_data['contractor_name'] = tenant_settings.contractor_name
                if tenant_settings.contractor_name_en:
                    validated_data['contractor_name_en'] = tenant_settings.contractor_name_en
                if tenant_settings.contractor_license_no:
                    validated_data['contractor_license_no'] = tenant_settings.contractor_license_no
                if tenant_settings.contractor_phone:
                    validated_data['contractor_phone'] = tenant_settings.contractor_phone
                if tenant_settings.contractor_email:
                    validated_data['contractor_email'] = tenant_settings.contractor_email
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نكمل بدون ملء البيانات
        
        # ✅ استعادة الملاك من حقل owners إلى Site Plan إذا لم تكن موجودة
        owners_data = validated_data.get("owners")
        if owners_data and isinstance(owners_data, list) and len(owners_data) > 0:
            try:
                siteplan = instance.project.siteplan
                # ✅ التحقق من وجود ملاك في Site Plan
                existing_owners_count = siteplan.owners.count()
                
                # ✅ إذا لم يكن هناك ملاك في Site Plan، نستعيدهم من الرخصة
                if existing_owners_count == 0:
                    from datetime import datetime
                    from decimal import Decimal
                    
                    for owner_data in owners_data:
                        # ✅ تحويل التواريخ من string إلى date objects
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
                        
                        # ✅ تحويل share_percent إلى Decimal
                        share_percent = owner_data.get("share_percent", "100.00")
                        if isinstance(share_percent, str):
                            try:
                                share_percent = Decimal(share_percent)
                            except:
                                share_percent = Decimal("100.00")
                        elif not isinstance(share_percent, Decimal):
                            share_percent = Decimal(str(share_percent))
                        
                        # ✅ تحويل is_authorized إلى boolean
                        is_authorized = owner_data.get("is_authorized", False)
                        if isinstance(is_authorized, str):
                            is_authorized = is_authorized.lower() in ("true", "1", "yes")
                        elif not isinstance(is_authorized, bool):
                            is_authorized = bool(is_authorized)
                        
                        # ✅ إنشاء المالك في Site Plan
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
                            is_authorized=is_authorized,  # ✅ المالك المفوض
                        )
                    
                    # ✅ تحديث اسم المشروع بعد استعادة الملاك
                    siteplan.refresh_from_db()
                    # ✅ استخدام نفس الدالة من SitePlanSerializer (instance method)
                    serializer_instance = SitePlanSerializer()
                    serializer_instance._update_project_name_from_owners(siteplan)
                    
                    # ✅ تحديث snapshot في الرخصة
                    instance.siteplan_snapshot = build_siteplan_snapshot(siteplan)
                    instance.save(update_fields=["siteplan_snapshot"])
                    
            except SitePlan.DoesNotExist:
                pass
            except Exception as e:
                # ✅ في حالة الخطأ، نكمل التحديث العادي
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error restoring owners from license to siteplan: {e}")
        
        # ✅ التعامل مع ملف رخصة البناء لتجنب إضافة لاحقة على الاسم
        file_obj = validated_data.get("building_license_file")
        if file_obj and isinstance(file_obj, (InMemoryUploadedFile, UploadedFile)):
            if instance.building_license_file:
                try:
                    instance.building_license_file.delete(save=False)
                except Exception:
                    pass

        # ✅ تحديث باقي الحقول
        return super().update(instance, validated_data)

# =========================
# Contract
# =========================
class ContractSerializer(serializers.ModelSerializer):
    # ✅ owners قابلة للتحرير وتُحفظ في قاعدة البيانات
    owners = serializers.ListField(
        child=serializers.DictField(allow_empty=True), 
        required=False,
        allow_empty=True,
        allow_null=True
    )
    license_snapshot = serializers.JSONField(read_only=True)
    
    # ✅ إرجاع start_order_exists بناءً على وجود الملف أو التاريخ
    start_order_exists = serializers.SerializerMethodField()
    
    # الملفات
    contract_file = serializers.FileField(required=False, allow_null=True)
    contract_appendix_file = serializers.FileField(required=False, allow_null=True)
    contract_explanation_file = serializers.FileField(required=False, allow_null=True)
    start_order_file = serializers.FileField(required=False, allow_null=True)
    
    # ✅ المرفقات الثابتة
    quantities_table_file = serializers.FileField(required=False, allow_null=True)
    approved_materials_table_file = serializers.FileField(required=False, allow_null=True)
    price_offer_file = serializers.FileField(required=False, allow_null=True)
    contractual_drawings_file = serializers.FileField(required=False, allow_null=True)
    general_specifications_file = serializers.FileField(required=False, allow_null=True)
    
    # ✅ Pattern لاستخراج owners من FormData (مثل SitePlanSerializer)
    _owners_key_re = re.compile(r"^owners\[(\d+)\]\[(\w+)\]$")
    
    # ✅ Pattern لاستخراج attachments من FormData
    _attachments_key_re = re.compile(r"^attachments\[(\d+)\]\[(\w+)\]$")

    class Meta:
        model = Contract
        fields = [
            "id", "project",
            # تصنيف ونوع
            "contract_classification", "contract_type",
            # تفاصيل
            "tender_no", "contract_date",
            # الأطراف
            "owners",  # write-only
            "contractor_name", "contractor_name_en", "contractor_trade_license",
            "contractor_phone", "contractor_email",
            # القيم والمدة
            "total_project_value", "total_bank_value", "total_owner_value", "project_duration_months",
            "start_order_date", "project_end_date",
            # أمر المباشرة
            "start_order_exists",
            # أتعاب (المالك)
            "owner_includes_consultant", "owner_fee_design_percent", "owner_fee_supervision_percent",
            "owner_fee_extra_mode", "owner_fee_extra_value",
            # أتعاب (البنك)
            "bank_includes_consultant", "bank_fee_design_percent", "bank_fee_supervision_percent",
            "bank_fee_extra_mode", "bank_fee_extra_value",
            # الملفات
            "contract_file", "contract_appendix_file", "contract_explanation_file", "start_order_file",
            # المرفقات الثابتة
            "quantities_table_file", "approved_materials_table_file", "price_offer_file",
            "contractual_drawings_file", "general_specifications_file",
            # المرفقات الديناميكية
            "attachments",
            # التمديدات
            "extensions",
            # الملاحظات
            "general_notes",
            "start_order_notes",
            # اللقطة
            "license_snapshot",
            # أمر المباشرة
            "start_order_exists",
            "created_at", "updated_at",
        ]
        read_only_fields = ["project", "license_snapshot", "start_order_exists", "created_at", "updated_at"]

    def to_internal_value(self, data):
        """دعم owners كسلسلة JSON في multipart: owners='[{"owner_name_ar":"..."}, ...]'"""
        import logging
        logger = logging.getLogger(__name__)
        
        # ✅ استخراج owners من البيانات أولاً قبل أي تعديل
        # ⚠️ لا نستخدم copy() لأن QueryDict قد يحتوي على ملفات غير قابلة للنسخ (BufferedRandom)
        # بدلاً من ذلك، نستخدم data مباشرة ونزيل owners قبل استدعاء super()
        
        # ✅ استخراج owners من البيانات
        owners_raw = None
        if hasattr(self, 'initial_data') and self.initial_data:
            owners_raw = self.initial_data.get("owners")
        
        # ✅ إذا لم نجد owners في initial_data، نحاول من data مباشرة
        if owners_raw is None and hasattr(data, 'get'):
            owners_raw = data.get("owners")
        
        # ✅ محاولة استخراج owners من FormData (owners[0][...]) إذا لم تكن موجودة كـ JSON string
        if owners_raw is None:
            req = self.context.get("request")
            if req:
                try:
                    # ✅ محاولة من req._request.POST (البيانات النصية من FormData)
                    post_data = None
                    if hasattr(req, '_request') and hasattr(req._request, 'POST'):
                        post_data = req._request.POST
                    elif hasattr(req, 'POST'):
                        post_data = req.POST
                    
                    if post_data and hasattr(post_data, 'get'):
                        buckets = {}
                        for k in post_data.keys():
                            k_str = str(k)
                            m = self._owners_key_re.match(k_str)
                            if m:
                                idx = int(m.group(1))
                                key = m.group(2)
                                buckets.setdefault(idx, {})[key] = post_data.get(k)
                        
                        if buckets:
                            owners_raw = [buckets[i] for i in sorted(buckets.keys())]
                            logger.info(f"ContractSerializer: Extracted {len(owners_raw)} owners from FormData keys")
                except Exception as e:
                    logger.warning(f"ContractSerializer: Error extracting owners from FormData: {e}")
        
        # ✅ معالجة owners وتحويلها إلى list من dictionaries
        owners_parsed = []
        if owners_raw is not None:
            if isinstance(owners_raw, str):
                # ✅ إذا كانت string فارغة، نستخدم قائمة فارغة
                if owners_raw.strip() == "":
                    owners_parsed = []
                else:
                    try:
                        parsed = json.loads(owners_raw)
                        if isinstance(parsed, list):
                            owners_parsed = parsed
                        else:
                            owners_parsed = []
                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        logger.warning(f"ContractSerializer: Failed to parse owners JSON: {e}")
                        owners_parsed = []
            elif isinstance(owners_raw, list):
                owners_parsed = owners_raw
            else:
                owners_parsed = []
        
        # ✅ إزالة owners من data قبل استدعاء super() لتجنب أخطاء التحقق من النوع
        # ⚠️ نستخدم data مباشرة (بدون نسخ) لأن QueryDict يحتوي على ملفات غير قابلة للنسخ
        owners_removed = False
        owners_value = None
        try:
            from django.http import QueryDict
            if isinstance(data, QueryDict):
                # ✅ حفظ قيمة owners ثم إزالتها
                if "owners" in data:
                    owners_value = data.get("owners")
                    # ✅ إزالة owners من QueryDict
                    data._mutable = True
                    data.pop("owners", None)
                    owners_removed = True
            elif isinstance(data, dict):
                owners_value = data.pop("owners", None)
                owners_removed = True
            elif hasattr(data, 'pop'):
                try:
                    owners_value = data.pop("owners", None)
                    owners_removed = True
                except:
                    pass
        except Exception as e:
            logger.warning(f"Error removing owners from data: {e}")
        
        # ✅ استدعاء super() بدون owners
        ret = super().to_internal_value(data)
        
        # ✅ إعادة owners إلى data إذا كنا قد أزلناها (للمحافظة على البيانات الأصلية)
        if owners_removed and owners_value is not None:
            try:
                from django.http import QueryDict
                if isinstance(data, QueryDict):
                    data._mutable = True
                    data.appendlist("owners", owners_value)
                elif isinstance(data, dict):
                    data["owners"] = owners_value
            except:
                pass
        
        # ✅ إضافة owners بعد التحقق (كـ list من dictionaries)
        ret["owners"] = owners_parsed if isinstance(owners_parsed, list) else []
        
        # ✅ التأكد من أن owners هي list دائماً
        if "owners" in ret and not isinstance(ret["owners"], list):
            ret["owners"] = []
        
        # ✅ معالجة الحقول الرقمية والمنطقية التي قد تأتي كسلسلة من FormData
        numeric_fields = [
            "total_project_value", "total_bank_value", "total_owner_value",
            "project_duration_months", "owner_fee_design_percent", "owner_fee_supervision_percent",
            "owner_fee_extra_value", "bank_fee_design_percent", "bank_fee_supervision_percent",
            "bank_fee_extra_value"
        ]
        for field in numeric_fields:
            if field in ret and isinstance(ret.get(field), str):
                try:
                    val = ret[field]
                    if val.strip() == "":
                        ret[field] = None
                    else:
                        ret[field] = float(val)
                except (ValueError, TypeError, AttributeError):
                    pass
        
        boolean_fields = ["owner_includes_consultant", "bank_includes_consultant"]
        for field in boolean_fields:
            if field in ret and isinstance(ret.get(field), str):
                ret[field] = ret[field].lower() in ("true", "1", "yes", "on")
        
        # ✅ معالجة attachments
        attachments_raw = None
        if hasattr(self, 'initial_data') and self.initial_data:
            attachments_raw = self.initial_data.get("attachments")
        if attachments_raw is None and hasattr(data, 'get'):
            attachments_raw = data.get("attachments")
        
        attachments_parsed = []
        if attachments_raw is not None:
            if isinstance(attachments_raw, str):
                try:
                    parsed = json.loads(attachments_raw)
                    if isinstance(parsed, list):
                        attachments_parsed = parsed
                except (json.JSONDecodeError, ValueError, TypeError):
                    attachments_parsed = []
            elif isinstance(attachments_raw, list):
                attachments_parsed = attachments_raw
        
        # ✅ استخراج ملفات attachments من FormData
        req = self.context.get("request")
        if req:
            try:
                files_data = None
                if hasattr(req, '_request') and hasattr(req._request, 'FILES'):
                    files_data = req._request.FILES
                elif hasattr(req, 'FILES'):
                    files_data = req.FILES
                
                if files_data:
                    logger.info(f"🔍 Found {len(files_data)} files in FormData")
                    for key in files_data.keys():
                        logger.info(f"🔍 FormData key: {key}")
                        # ✅ البحث عن attachments[0][file], attachments[1][file], إلخ
                        match = re.match(r"^attachments\[(\d+)\]\[file\]$", str(key))
                        if match:
                            idx = int(match.group(1))
                            if idx < len(attachments_parsed):
                                file_obj = files_data.get(key)
                                attachments_parsed[idx]["_file"] = file_obj
                                logger.info(f"✅ Linked file to attachments_parsed[{idx}]: {file_obj.name if file_obj else 'None'}")
                            else:
                                logger.warning(f"⚠️ Attachment index {idx} out of range (len={len(attachments_parsed)})")
                        else:
                            logger.debug(f"🔍 Key '{key}' doesn't match attachments pattern")
            except Exception as e:
                logger.warning(f"Error extracting attachment files: {e}", exc_info=True)
        
        ret["attachments"] = attachments_parsed if isinstance(attachments_parsed, list) else []
        
        # ✅ معالجة extensions
        extensions_raw = None
        if hasattr(self, 'initial_data') and self.initial_data:
            extensions_raw = self.initial_data.get("extensions")
        if extensions_raw is None and hasattr(data, 'get'):
            extensions_raw = data.get("extensions")
        
        extensions_parsed = []
        if extensions_raw is not None:
            if isinstance(extensions_raw, str):
                try:
                    parsed = json.loads(extensions_raw)
                    if isinstance(parsed, list):
                        extensions_parsed = parsed
                except (json.JSONDecodeError, ValueError, TypeError):
                    extensions_parsed = []
            elif isinstance(extensions_raw, list):
                extensions_parsed = extensions_raw
        
        # ✅ استخراج ملفات التمديدات من FormData (مثل attachments)
        files_data = {}
        req = self.context.get("request")
        if req:
            try:
                files = None
                if hasattr(req, '_request') and hasattr(req._request, 'FILES'):
                    files = req._request.FILES
                elif hasattr(req, 'FILES'):
                    files = req.FILES
                
                if files:
                    import re
                    pattern = re.compile(r"^extensions\[(\d+)\]\[file\]$")
                    for key in files.keys():
                        m = pattern.match(str(key))
                        if m:
                            idx = int(m.group(1))
                            files_data[idx] = files.get(key)
            except Exception as e:
                logger.warning(f"Error extracting extension files: {e}")
        
        # ✅ تنظيف extensions - التأكد من أن كل extension يحتوي على الحقول المطلوبة
        cleaned_extensions = []
        for idx, ext in enumerate(extensions_parsed):
            if isinstance(ext, dict):
                cleaned_ext = {
                    "reason": str(ext.get("reason", "")).strip(),
                    "days": int(ext.get("days", 0)) if ext.get("days") is not None else 0,
                    "months": int(ext.get("months", 0)) if ext.get("months") is not None else 0,
                    "extension_date": str(ext.get("extension_date", "")).strip() if ext.get("extension_date") else None,
                    "approval_number": str(ext.get("approval_number", "")).strip() if ext.get("approval_number") else None,
                    "file_url": str(ext.get("file_url", "")).strip() if ext.get("file_url") else None,
                    "file_name": str(ext.get("file_name", "")).strip() if ext.get("file_name") else None,
                }
                # ✅ إضافة ملف إذا كان موجوداً في FormData
                if idx in files_data:
                    cleaned_ext["_file"] = files_data[idx]
                # ✅ إضافة فقط إذا كان له بيانات (سبب أو مدة أو تاريخ أو رقم اعتماد أو ملف)
                hasData = (
                    cleaned_ext["reason"] or 
                    cleaned_ext["days"] > 0 or 
                    cleaned_ext["months"] > 0 or 
                    cleaned_ext["extension_date"] or 
                    cleaned_ext["approval_number"] or 
                    cleaned_ext.get("_file")
                )
                if hasData:
                    cleaned_extensions.append(cleaned_ext)
        
        ret["extensions"] = cleaned_extensions
        
        return ret

    def validate(self, attrs):
        total = attrs.get("total_project_value") or getattr(self.instance, "total_project_value", None)
        bank  = attrs.get("total_bank_value")  or getattr(self.instance, "total_bank_value", 0)
        if total is not None and float(total) <= 0:
            raise serializers.ValidationError({"total_project_value": "يجب أن يكون أكبر من صفر."})
        if bank is not None and float(bank) < 0:
            raise serializers.ValidationError({"total_bank_value": "لا يمكن أن يكون سالبًا."})
        return attrs

    def get_start_order_exists(self, obj):
        """حساب start_order_exists بناءً على وجود الملف أو التاريخ"""
        return bool(obj.start_order_file or obj.start_order_date)

    def to_representation(self, instance):
        """ملء بيانات المقاول من TenantSettings عند القراءة دائماً (Single Source of Truth)"""
        representation = super().to_representation(instance)
        
        # ✅ ملء بيانات المقاول من TenantSettings دائماً (Single Source of Truth)
        project = instance.project
        if project and project.tenant:
            try:
                from authentication.models import TenantSettings
                tenant_settings = TenantSettings.objects.get(tenant=project.tenant)
                
                # ✅ نستخدم بيانات TenantSettings دائماً لضمان التحديث التلقائي
                if tenant_settings.contractor_name:
                    representation['contractor_name'] = tenant_settings.contractor_name
                if tenant_settings.contractor_name_en:
                    representation['contractor_name_en'] = tenant_settings.contractor_name_en
                if tenant_settings.contractor_license_no:
                    representation['contractor_trade_license'] = tenant_settings.contractor_license_no
                if tenant_settings.contractor_phone:
                    representation['contractor_phone'] = tenant_settings.contractor_phone
                if tenant_settings.contractor_email:
                    representation['contractor_email'] = tenant_settings.contractor_email
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نكمل بدون ملء البيانات
        
        return representation

    def _fill_snapshot(self, contract: Contract):
        try:
            lic = contract.project.license
        except BuildingLicense.DoesNotExist:
            # ✅ إذا لم تكن الرخصة موجودة، نضع snapshot فارغ
            contract.license_snapshot = {}
            contract.save(update_fields=["license_snapshot"])
            return
        try:
            contract.license_snapshot = build_license_snapshot(lic)
            contract.save(update_fields=["license_snapshot"])
        except Exception as e:
            # ✅ في حالة أي خطأ، نضع snapshot فارغ بدلاً من إيقاف العملية
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error building license snapshot: {e}", exc_info=True)
            contract.license_snapshot = {}
            contract.save(update_fields=["license_snapshot"])

    def create(self, validated_data):
        # ✅ ملء بيانات المقاول من TenantSettings تلقائياً إذا لم تكن موجودة
        project = validated_data.get('project')
        if project and project.tenant:
            try:
                from authentication.models import TenantSettings
                tenant_settings = TenantSettings.objects.get(tenant=project.tenant)
                # ✅ ملء بيانات المقاول من TenantSettings إذا كانت فارغة
                if not validated_data.get('contractor_name') and tenant_settings.contractor_name:
                    validated_data['contractor_name'] = tenant_settings.contractor_name
                if not validated_data.get('contractor_name_en') and tenant_settings.contractor_name_en:
                    validated_data['contractor_name_en'] = tenant_settings.contractor_name_en
                if not validated_data.get('contractor_trade_license') and tenant_settings.contractor_license_no:
                    validated_data['contractor_trade_license'] = tenant_settings.contractor_license_no
                if not validated_data.get('contractor_phone') and tenant_settings.contractor_phone:
                    validated_data['contractor_phone'] = tenant_settings.contractor_phone
                if not validated_data.get('contractor_email') and tenant_settings.contractor_email:
                    validated_data['contractor_email'] = tenant_settings.contractor_email
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نكمل بدون ملء البيانات
        
        # ✅ حفظ owners في قاعدة البيانات (قابلة للتحرير)
        owners_data = validated_data.pop("owners", [])
        attachments_data = validated_data.pop("attachments", [])
        extensions_data = validated_data.pop("extensions", [])
        
        try:
            obj = Contract.objects.create(**validated_data)
            
            # ✅ حفظ owners في قاعدة البيانات
            if owners_data and isinstance(owners_data, list):
                obj.owners = owners_data
                obj.save(update_fields=["owners"])
            
            # ✅ حفظ extensions في قاعدة البيانات
            if extensions_data and isinstance(extensions_data, list):
                saved_extensions = []
                for ext in extensions_data:
                    ext_dict = {
                        "reason": ext.get("reason", ""),
                        "days": ext.get("days", 0),
                        "months": ext.get("months", 0),
                        "extension_date": ext.get("extension_date"),
                        "approval_number": ext.get("approval_number"),
                        "file_url": None,
                        "file_name": None,
                    }
                    # ✅ إذا كان هناك ملف جديد
                    if "_file" in ext and ext["_file"]:
                        from django.core.files.storage import default_storage
                        file_obj = ext["_file"]
                        file_path = default_storage.save(f"contracts/extensions/{obj.id}/{file_obj.name}", file_obj)
                        ext_dict["file_url"] = default_storage.url(file_path)
                        ext_dict["file_name"] = file_obj.name
                    # ✅ إذا كان هناك file_url موجود (من extension قديم)
                    elif ext.get("file_url"):
                        ext_dict["file_url"] = ext.get("file_url")
                        ext_dict["file_name"] = ext.get("file_name")
                    saved_extensions.append(ext_dict)
                obj.extensions = saved_extensions
                obj.save(update_fields=["extensions"])
            
            # ✅ حفظ المرفقات
            if attachments_data and isinstance(attachments_data, list):
                # ✅ استخراج ملفات attachments من FormData (نفس منطق to_internal_value و update)
                req = self.context.get("request")
                files_data = None
                if req:
                    try:
                        if hasattr(req, '_request') and hasattr(req._request, 'FILES'):
                            files_data = req._request.FILES
                        elif hasattr(req, 'FILES'):
                            files_data = req.FILES
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error extracting attachment files in create: {e}")
                
                # ✅ ربط الملفات بالمرفقات
                if files_data:
                    for key in files_data.keys():
                        # ✅ البحث عن attachments[0][file], attachments[1][file], إلخ
                        match = re.match(r"^attachments\[(\d+)\]\[file\]$", str(key))
                        if match:
                            idx = int(match.group(1))
                            if idx < len(attachments_data):
                                attachments_data[idx]["_file"] = files_data.get(key)
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"✅ Linked file to attachment[{idx}]: {files_data.get(key).name if files_data.get(key) else 'None'}")
                
                saved_attachments = []
                for idx, att in enumerate(attachments_data):
                    att_dict = {
                        "type": att.get("type", "main_contract"),
                        "date": att.get("date"),
                        "notes": att.get("notes", ""),
                        "file_url": None,
                        "file_name": None,
                    }
                    # ✅ إذا كان هناك ملف جديد
                    if "_file" in att and att["_file"]:
                        from django.core.files.storage import default_storage
                        file_obj = att["_file"]
                        file_path = default_storage.save(f"contracts/attachments/{obj.id}/{file_obj.name}", file_obj)
                        att_dict["file_url"] = default_storage.url(file_path)
                        att_dict["file_name"] = file_obj.name
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"✅ Saved attachment[{idx}] file: {file_obj.name} -> {att_dict['file_url']}")
                    # ✅ إذا كان هناك file_url موجود (من attachment قديم)
                    elif att.get("file_url"):
                        att_dict["file_url"] = att.get("file_url")
                        att_dict["file_name"] = att.get("file_name")
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"⚠️ Attachment[{idx}] has no file: type={att.get('type')}, _file={'_file' in att}, file_url={att.get('file_url')}")
                    saved_attachments.append(att_dict)
                obj.attachments = saved_attachments
                obj.save(update_fields=["attachments"])
            
            # ✅ محاولة ملء snapshot - إذا فشلت، نكمل بدون snapshot
            try:
                self._fill_snapshot(obj)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error filling snapshot in create: {e}", exc_info=True)
            return obj
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating contract: {e}", exc_info=True)
            raise

    def update(self, instance, validated_data):
        # ✅ ملء بيانات المقاول من TenantSettings تلقائياً (تحديث تلقائي)
        project = instance.project
        if project and project.tenant:
            try:
                from authentication.models import TenantSettings
                tenant_settings = TenantSettings.objects.get(tenant=project.tenant)
                # ✅ نستخدم بيانات TenantSettings دائماً لضمان التحديث التلقائي
                if tenant_settings.contractor_name:
                    validated_data['contractor_name'] = tenant_settings.contractor_name
                if tenant_settings.contractor_name_en:
                    validated_data['contractor_name_en'] = tenant_settings.contractor_name_en
                if tenant_settings.contractor_license_no:
                    validated_data['contractor_trade_license'] = tenant_settings.contractor_license_no
                if tenant_settings.contractor_phone:
                    validated_data['contractor_phone'] = tenant_settings.contractor_phone
                if tenant_settings.contractor_email:
                    validated_data['contractor_email'] = tenant_settings.contractor_email
            except TenantSettings.DoesNotExist:
                pass  # إذا لم تكن هناك إعدادات، نكمل بدون ملء البيانات
        
        # ✅ تحديث owners في قاعدة البيانات (قابلة للتحرير)
        owners_data = validated_data.pop("owners", None)
        attachments_data = validated_data.pop("attachments", None)
        extensions_data = validated_data.pop("extensions", None)
        
        try:
            updated = super().update(instance, validated_data)
            
            # ✅ تحديث owners في قاعدة البيانات
            if owners_data is not None and isinstance(owners_data, list):
                updated.owners = owners_data
                updated.save(update_fields=["owners"])
            
            # ✅ تحديث extensions في قاعدة البيانات
            if extensions_data is not None and isinstance(extensions_data, list):
                saved_extensions = []
                for ext in extensions_data:
                    ext_dict = {
                        "reason": ext.get("reason", ""),
                        "days": ext.get("days", 0),
                        "months": ext.get("months", 0),
                        "extension_date": ext.get("extension_date"),
                        "approval_number": ext.get("approval_number"),
                        "file_url": None,
                        "file_name": None,
                    }
                    # ✅ إذا كان هناك ملف جديد
                    if "_file" in ext and ext["_file"]:
                        from django.core.files.storage import default_storage
                        file_obj = ext["_file"]
                        # ✅ حذف الملف القديم إذا كان موجوداً
                        old_ext = None
                        if updated.extensions and isinstance(updated.extensions, list) and len(updated.extensions) > len(saved_extensions):
                            old_ext = updated.extensions[len(saved_extensions)]
                            if old_ext and old_ext.get("file_url"):
                                try:
                                    old_path = old_ext["file_url"].replace(default_storage.url(""), "")
                                    if default_storage.exists(old_path):
                                        default_storage.delete(old_path)
                                except:
                                    pass
                        file_path = default_storage.save(f"contracts/extensions/{updated.id}/{file_obj.name}", file_obj)
                        ext_dict["file_url"] = default_storage.url(file_path)
                        ext_dict["file_name"] = file_obj.name
                    # ✅ إذا كان هناك file_url موجود (من extension قديم)
                    elif ext.get("file_url"):
                        ext_dict["file_url"] = ext.get("file_url")
                        ext_dict["file_name"] = ext.get("file_name")
                    saved_extensions.append(ext_dict)
                updated.extensions = saved_extensions
                updated.save(update_fields=["extensions"])
            
            # ✅ تحديث المرفقات إذا كانت موجودة
            if attachments_data is not None and isinstance(attachments_data, list):
                # ✅ استخراج ملفات attachments من FormData (نفس منطق to_internal_value)
                req = self.context.get("request")
                files_data = None
                if req:
                    try:
                        if hasattr(req, '_request') and hasattr(req._request, 'FILES'):
                            files_data = req._request.FILES
                        elif hasattr(req, 'FILES'):
                            files_data = req.FILES
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error extracting attachment files in update: {e}")
                
                # ✅ ربط الملفات بالمرفقات
                if files_data:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"🔍 Found {len(files_data)} files in FormData (update)")
                    for key in files_data.keys():
                        logger.info(f"🔍 FormData key (update): {key}")
                        # ✅ البحث عن attachments[0][file], attachments[1][file], إلخ
                        match = re.match(r"^attachments\[(\d+)\]\[file\]$", str(key))
                        if match:
                            idx = int(match.group(1))
                            if idx < len(attachments_data):
                                file_obj = files_data.get(key)
                                attachments_data[idx]["_file"] = file_obj
                                logger.info(f"✅ Linked file to attachments_data[{idx}] (update): {file_obj.name if file_obj else 'None'}")
                            else:
                                logger.warning(f"⚠️ Attachment index {idx} out of range (len={len(attachments_data)})")
                        else:
                            logger.debug(f"🔍 Key '{key}' doesn't match attachments pattern (update)")
                
                saved_attachments = []
                for idx, att in enumerate(attachments_data):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"🔍 Processing attachment[{idx}] (update): type={att.get('type')}, has_file={'_file' in att}, file_url={att.get('file_url')}")
                    
                    att_dict = {
                        "type": att.get("type", "main_contract"),
                        "date": att.get("date"),
                        "notes": att.get("notes", ""),
                        "file_url": att.get("file_url"),  # الحفاظ على الملف القديم
                        "file_name": att.get("file_name"),
                    }
                    # ✅ إذا كان هناك ملف جديد
                    if "_file" in att and att["_file"]:
                        from django.core.files.storage import default_storage
                        file_obj = att["_file"]
                        # ✅ حذف الملف القديم إذا كان موجوداً
                        old_att = None
                        if updated.attachments and isinstance(updated.attachments, list) and len(updated.attachments) > len(saved_attachments):
                            old_att = updated.attachments[len(saved_attachments)]
                            if old_att and old_att.get("file_url"):
                                try:
                                    old_path = old_att["file_url"].replace(default_storage.url(""), "")
                                    if default_storage.exists(old_path):
                                        default_storage.delete(old_path)
                                except:
                                    pass
                        file_path = default_storage.save(f"contracts/attachments/{instance.id}/{file_obj.name}", file_obj)
                        att_dict["file_url"] = default_storage.url(file_path)
                        att_dict["file_name"] = file_obj.name
                        logger.info(f"✅ Saved attachment[{idx}] file (update): {file_obj.name} -> {att_dict['file_url']}")
                    # ✅ إذا كان هناك file_url موجود (من attachment قديم) ولم يكن هناك ملف جديد
                    elif att.get("file_url"):
                        att_dict["file_url"] = att.get("file_url")
                        att_dict["file_name"] = att.get("file_name")
                        logger.info(f"✅ Preserved attachment[{idx}] existing file (update): {att_dict['file_url']}")
                    else:
                        logger.warning(f"⚠️ Attachment[{idx}] has no file (update): type={att.get('type')}, _file={'_file' in att}, file_url={att.get('file_url')}")
                    saved_attachments.append(att_dict)
                updated.attachments = saved_attachments
                updated.save(update_fields=["attachments"])
            
            # ✅ محاولة تحديث snapshot - إذا فشلت، نكمل بدون snapshot
            try:
                self._fill_snapshot(updated)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error filling snapshot in update: {e}", exc_info=True)
            return updated
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating contract: {e}", exc_info=True)
            raise


# =========================
# Awarding
# =========================
class AwardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Awarding
        fields = [
            "id", "project",
            "award_date",
            "consultant_registration_number",
            "project_number",
            "contractor_registration_number",
            "awarding_file",
            "created_at", "updated_at",
        ]
        read_only_fields = ["project", "created_at", "updated_at"]


# =========================
# Variation (Price Change Order)
# =========================
class VariationSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    variation_invoice_file = serializers.SerializerMethodField()
    
    class Meta:
        model = Variation
        fields = [
            "id", "project",
            "variation_number", "description",
            "final_amount", "consultant_fees", "contractor_engineer_fees",
            "total_amount", "discount",
            "net_amount", "vat", "net_amount_with_vat",
            "variation_invoice_file",
            "amount", "approval_date", "approved_by", "attachments",
            "project_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
    
    def validate_description(self, value):
        """Ensure description is a string, not None"""
        return value or ""
    
    def validate_approved_by(self, value):
        """Ensure approved_by is a string, not None"""
        return value or ""
    
    def validate_attachments(self, value):
        """Ensure attachments is a list"""
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return value
    
    def validate_variation_number(self, value):
        """Convert empty string to None for auto-generation"""
        return value if value and value.strip() else None
    
    def get_project_name(self, obj):
        if not obj or not obj.project:
            return None
        try:
            project = obj.project
            if project.name and project.name.strip():
                return project.name
            return f"Project #{project.id}"
        except Exception:
            return None
    
    def get_variation_invoice_file(self, obj):
        if obj.variation_invoice_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.variation_invoice_file.url)
            return obj.variation_invoice_file.url
        return None
    
    def create(self, validated_data):
        """Auto-generate variation_number if not provided and calculate consultant_fees from percentage"""
        if not validated_data.get('variation_number'):
            # Generate unique variation number
            import uuid
            validated_data['variation_number'] = f"VAR-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate consultant_fees from percentage if provided
        if 'consultant_fees_percentage' in validated_data and 'final_amount' in validated_data:
            from decimal import Decimal
            final_amount = validated_data.get('final_amount', Decimal('0'))
            percentage = validated_data.get('consultant_fees_percentage', Decimal('0'))
            validated_data['consultant_fees'] = final_amount * (percentage / Decimal('100'))
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Calculate consultant_fees from percentage if percentage is updated"""
        # Calculate consultant_fees from percentage if percentage is provided
        if 'consultant_fees_percentage' in validated_data:
            from decimal import Decimal
            final_amount = validated_data.get('final_amount', instance.final_amount)
            percentage = validated_data.get('consultant_fees_percentage', Decimal('0'))
            validated_data['consultant_fees'] = final_amount * (percentage / Decimal('100'))
        
        return super().update(instance, validated_data)


# =========================
# Invoice
# =========================
    def create(self, validated_data):
        """Auto-generate invoice_number if not provided"""
        # Convert empty string to None
        if not validated_data.get('invoice_number'):
            validated_data['invoice_number'] = None
        
        # Generate invoice number if still None
        if validated_data.get('invoice_number') is None:
            import datetime
            project_id = validated_data.get('project').id if validated_data.get('project') else 'X'
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            # Add random suffix to ensure uniqueness
            import random
            random_suffix = random.randint(1000, 9999)
            validated_data['invoice_number'] = f"INV-{project_id}-{timestamp}-{random_suffix}"
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Handle invoice_number update"""
        # Convert empty string to None
        if 'invoice_number' in validated_data:
            if validated_data['invoice_number'] == "":
                validated_data['invoice_number'] = None
        
        return super().update(instance, validated_data)


class ActualInvoiceSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    payment_id = serializers.SerializerMethodField()
    items = serializers.JSONField(default=list, required=False, allow_null=True)
    
    class Meta:
        model = ActualInvoice
        fields = [
            "id", "project", "payment",
            "amount", "invoice_date", "invoice_number", "description", "items",
            "project_name", "payment_id",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "payment_id"]
    
    def to_representation(self, instance):
        """Ensure items is always returned as a list"""
        try:
            data = super().to_representation(instance)
        except Exception as e:
            # ✅ Handle case where items field doesn't exist in database
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error in to_representation for ActualInvoice {instance.id}: {e}")
            # Try to get basic fields manually
            data = {
                'id': instance.id,
                'project': instance.project_id,
                'payment': instance.payment_id if instance.payment else None,
                'amount': str(instance.amount),
                'invoice_date': instance.invoice_date.isoformat() if instance.invoice_date else None,
                'invoice_number': instance.invoice_number or None,
                'description': instance.description or '',
                'items': [],  # Default to empty array
                'created_at': instance.created_at.isoformat() if instance.created_at else None,
                'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
            }
            # Add computed fields
            data['project_name'] = self.get_project_name(instance)
            data['payment_id'] = self.get_payment_id(instance)
        
        # ✅ Ensure items is always an array, even if None or missing
        if 'items' not in data or data['items'] is None:
            data['items'] = []
        elif not isinstance(data['items'], list):
            data['items'] = [data['items']] if data['items'] else []
        return data
    
    def validate(self, data):
        """Validate that project is provided"""
        if 'project' not in data:
            raise serializers.ValidationError({
                'project': 'Project is required.'
            })
        
        return data
    
    def validate_invoice_number(self, value):
        """Convert empty string to None to avoid UNIQUE constraint violation"""
        if value == "" or value is None:
            return None
        return value
    
    def create(self, validated_data):
        """Auto-generate invoice_number if not provided"""
        # Convert empty string to None
        if not validated_data.get('invoice_number'):
            validated_data['invoice_number'] = None
        
        # Generate invoice number if still None
        if validated_data.get('invoice_number') is None:
            import datetime
            project_id = validated_data.get('project').id if validated_data.get('project') else 'X'
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            # Add random suffix to ensure uniqueness
            import random
            random_suffix = random.randint(1000, 9999)
            validated_data['invoice_number'] = f"ACT-{project_id}-{timestamp}-{random_suffix}"
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Handle invoice_number update"""
        # Convert empty string to None
        if 'invoice_number' in validated_data:
            if validated_data['invoice_number'] == "":
                validated_data['invoice_number'] = None
        
        return super().update(instance, validated_data)
    
    def get_payment_id(self, obj):
        """Get payment ID if payment exists"""
        if obj.payment:
            return obj.payment.id
        return None
    
    def get_project_name(self, obj):
        if not obj or not obj.project:
            return None
        try:
            project = obj.project
            if project.name and project.name.strip():
                return project.name
            return f"Project #{project.id}"
        except Exception:
            return None


# =========================
# Payment
# =========================
class PaymentSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    actual_invoice_id = serializers.SerializerMethodField()
    deposit_slip = serializers.SerializerMethodField()
    invoice_file = serializers.SerializerMethodField()
    receipt_voucher = serializers.SerializerMethodField()
    bank_payment_attachments = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            "id", "project",
            "payer", "payment_method",
            "amount", "date", "description",
            "recipient_account_number", "sender_account_number", "transferor_name",
            "cheque_holder_name", "cheque_account_number", "cheque_date",
            "project_financial_account", "completion_percentage", "bank_payment_attachments",
            "deposit_slip", "invoice_file", "receipt_voucher",
            "actual_invoice_id",
            "project_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "actual_invoice_id"]
    
    def get_deposit_slip(self, obj):
        if obj.deposit_slip:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.deposit_slip.url)
            return obj.deposit_slip.url
        return None
    
    def get_invoice_file(self, obj):
        if obj.invoice_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.invoice_file.url)
            return obj.invoice_file.url
        return None
    
    def get_receipt_voucher(self, obj):
        if obj.receipt_voucher:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.receipt_voucher.url)
            return obj.receipt_voucher.url
        return None
    
    def get_bank_payment_attachments(self, obj):
        if obj.bank_payment_attachments:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.bank_payment_attachments.url)
            return obj.bank_payment_attachments.url
        return None
    
    def get_actual_invoice_id(self, obj):
        """Get actual_invoice ID via reverse relationship"""
        try:
            return obj.actual_invoice.id if hasattr(obj, 'actual_invoice') and obj.actual_invoice else None
        except Exception:
            return None
    
    def validate(self, data):
        """Validate payment method based on payer"""
        payer = data.get('payer', self.instance.payer if self.instance else 'owner')
        payment_method = data.get('payment_method', self.instance.payment_method if self.instance else None)
        
        if payer == 'bank':
            if payment_method and payment_method != 'bank_transfer':
                raise serializers.ValidationError({
                    'payment_method': 'Bank payments must use Bank Transfer only.'
                })
            # Force bank_transfer for bank payments
            data['payment_method'] = 'bank_transfer'
        elif payer == 'owner':
            if not payment_method:
                raise serializers.ValidationError({
                    'payment_method': 'Payment method is required for owner payments.'
                })
            valid_methods = ['cash_deposit', 'cash_office', 'bank_transfer', 'bank_cheque']
            if payment_method not in valid_methods:
                raise serializers.ValidationError({
                    'payment_method': f'Invalid payment method. Must be one of: {", ".join(valid_methods)}'
                })
        
        return data
    
    def get_project_name(self, obj):
        """الحصول على اسم المشروع - نفس منطق ProjectSerializer.get_display_name"""
        if not obj or not obj.project:
            return None
        
        try:
            project = obj.project
            
            # ✅ إذا كان project.name موجوداً، نستخدمه أولاً
            if project.name and project.name.strip():
                return project.name
            
            # ✅ إذا لم يكن هناك اسم محفوظ، نحاول حسابه من الملاك
            try:
                sp = project.siteplan
            except SitePlan.DoesNotExist:
                sp = None

            main_name = ""
            owners_count = 0
            if sp:
                qs = sp.owners.order_by("id")
                owners_count = qs.count()
                for o in qs:
                    ar = (o.owner_name_ar or "").strip()
                    en = (o.owner_name_en or "").strip()
                    if ar or en:
                        main_name = ar or en
                        break

            if main_name:
                return f"{main_name} وشركاؤه" if owners_count > 1 else main_name
            
            # ✅ إذا لم يكن هناك اسم ولا ملاك، نستخدم ID
            project_id = getattr(project, 'id', None)
            if project_id:
                return f"مشروع #{project_id}"
            return "مشروع جديد"
        except Exception as e:
            # ✅ في حالة أي خطأ، نرجع اسم بسيط
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting project name in PaymentSerializer: {e}")
            if obj.project:
                return obj.project.name or f"Project #{obj.project.id}"
            return None


# =========================
# Consultant
# =========================
class ConsultantSerializer(serializers.ModelSerializer):
    """Serializer للاستشاري"""
    image_url = serializers.SerializerMethodField()
    projects_count = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    
    class Meta:
        model = Consultant
        fields = [
            "id", "tenant",
            "name", "name_en", "license_no",
            "phone", "email", "address", "notes",
            "image", "image_url",
            "projects_count", "projects",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at", "projects_count", "projects"]
    
    def get_image_url(self, obj):
        """الحصول على رابط صورة الاستشاري"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    
    def get_projects_count(self, obj):
        """عدد المشاريع المرتبطة"""
        try:
            if hasattr(obj, 'projects'):
                return obj.projects.count()
            return 0
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error getting projects count for consultant {obj.id}: {e}")
            return 0
    
    def get_projects(self, obj):
        """قائمة المشاريع المرتبطة مع أدوار الاستشاري"""
        from .models import ProjectConsultant
        projects_data = []
        ROLE_CHOICES = [
            ('design', 'استشاري التصميم'),
            ('supervision', 'استشاري الإشراف'),
        ]
        try:
            if hasattr(obj, 'projects'):
                for pc in obj.projects.all():
                    try:
                        projects_data.append({
                            "project_id": pc.project.id,
                            "project_name": pc.project.name or f"Project #{pc.project.id}",
                            "role": pc.role,
                            "role_display": dict(ROLE_CHOICES).get(pc.role, pc.role),
                        })
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Error processing project consultant {pc.id}: {e}")
                        continue
        except Exception as e:
            # في حالة عدم وجود projects related، نرجع قائمة فارغة
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error getting projects for consultant {obj.id if hasattr(obj, 'id') else 'unknown'}: {e}")
        return projects_data
    
    def validate(self, data):
        """التحقق من عدم تكرار الاستشاري"""
        # tenant يتم تعيينه تلقائياً في perform_create، لذلك لا نحتاج للتحقق منه هنا
        tenant = self.instance.tenant if self.instance else None
        name = data.get('name', self.instance.name if self.instance else '')
        license_no = data.get('license_no', self.instance.license_no if self.instance else '')
        
        # التحقق من التكرار فقط إذا كان هناك tenant
        if tenant and name and license_no:
            existing = Consultant.objects.filter(
                tenant=tenant,
                name=name,
                license_no=license_no
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': 'Consultant with this name and license number already exists for this tenant.'
                })
        
        return data


class ProjectConsultantSerializer(serializers.ModelSerializer):
    """Serializer لربط الاستشاري بالمشروع"""
    consultant = ConsultantSerializer(read_only=True)
    consultant_id = serializers.PrimaryKeyRelatedField(
        queryset=Consultant.objects.all(),
        source='consultant',
        write_only=True
    )
    project_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectConsultant
        fields = [
            "id", "project", "consultant", "consultant_id", "role",
            "project_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "project_name"]
    
    def get_project_name(self, obj):
        """اسم المشروع"""
        if obj.project:
            return obj.project.name or f"Project #{obj.project.id}"
        return None
