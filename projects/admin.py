from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Project, SitePlan, SitePlanOwner, BuildingLicense, Contract, Awarding, Payment, Consultant, ProjectConsultant

# ---------- Project ----------
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_type", "status", "completion_pct", "created_at")
    list_filter = ("project_type", "status")
    search_fields = ("name",)

    def completion_pct(self, obj):
        # نحسبها من وجود SitePlan/License/Contract
        steps = 0
        done = 0
        for rel in ("siteplan", "license", "contract"):
            steps += 1
            if hasattr(obj, rel):
                done += 1
        pct = int(done / steps * 100) if steps else 0
        return f"{pct}%"
    completion_pct.short_description = "Completion"


# ---------- SitePlanOwner (الملاك) ----------
@admin.register(SitePlanOwner)
class SitePlanOwnerAdmin(admin.ModelAdmin):
    list_display = (
        "id", 
        "owner_name_display", 
        "project_link", 
        "nationality", 
        "phone", 
        "email", 
        "id_number", 
        "id_attachment_link", 
        "share_percent",
        "created_at"
    )
    list_filter = ("nationality", "right_hold_type", "siteplan__municipality", "siteplan__zone")
    search_fields = (
        "owner_name_ar", 
        "owner_name_en", 
        "id_number", 
        "phone", 
        "email",
        "siteplan__project__name",
        "siteplan__land_no"
    )
    readonly_fields = ("created_at", "updated_at", "id_attachment_preview")
    fieldsets = (
        ("معلومات المالك", {
            "fields": (
                "siteplan",
                "owner_name_ar",
                "owner_name_en",
                "nationality",
                "phone",
                "email",
            )
        }),
        ("معلومات الهوية", {
            "fields": (
                "id_number",
                "id_issue_date",
                "id_expiry_date",
                "id_attachment",
                "id_attachment_preview",
            )
        }),
        ("معلومات الملكية", {
            "fields": (
                "right_hold_type",
                "share_possession",
                "share_percent",
            )
        }),
        ("معلومات إضافية", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    def owner_name_display(self, obj):
        """عرض اسم المالك بالعربي أو الإنجليزي"""
        name = obj.owner_name_ar or obj.owner_name_en or "بدون اسم"
        return name
    owner_name_display.short_description = "اسم المالك"

    def project_link(self, obj):
        """رابط للمشروع المرتبط - يعرض اسم المشروع المحفوظ أو المحسوب من الملاك"""
        project = obj.siteplan.project
        url = reverse("admin:projects_project_change", args=[project.pk])
        
        # ✅ نستخدم اسم المشروع المحفوظ أولاً (هذا هو الاسم الصحيح الذي تم حفظه من الملاك)
        project_name = (project.name or "").strip()
        
        # ✅ إذا لم يكن هناك اسم محفوظ أو كان فارغاً، نحسبه من الملاك مباشرة
        if not project_name:
            siteplan = obj.siteplan
            owners = siteplan.owners.order_by("id")
            owners_count = owners.count()
            
            main_name = ""
            for owner in owners:
                ar = (owner.owner_name_ar or "").strip()
                en = (owner.owner_name_en or "").strip()
                if ar or en:
                    main_name = ar or en
                    break
            
            if main_name:
                project_name = f"{main_name} وشركاؤه" if owners_count > 1 else main_name
            else:
                project_name = f"Project #{project.id}"
        
        return format_html('<a href="{}">{}</a>', url, project_name)
    project_link.short_description = "المشروع"

    def id_attachment_link(self, obj):
        """رابط لتحميل ملف الهوية"""
        if obj.id_attachment:
            url = obj.id_attachment.url
            filename = obj.id_attachment.name.split('/')[-1]
            return format_html(
                '<a href="{}" target="_blank">📄 {}</a>',
                url,
                filename
            )
        return "—"
    id_attachment_link.short_description = "ملف الهوية"

    def id_attachment_preview(self, obj):
        """معاينة ملف الهوية"""
        if obj.id_attachment:
            url = obj.id_attachment.url
            filename = obj.id_attachment.name.split('/')[-1]
            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
            
            if file_ext in ['jpg', 'jpeg', 'png', 'gif']:
                return format_html(
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; padding: 5px;" />'
                    '</a><br><a href="{}" target="_blank">📥 تحميل الملف</a>',
                    url, url, url
                )
            else:
                return format_html(
                    '<a href="{}" target="_blank">📄 {} (تحميل)</a>',
                    url, filename
                )
        return "لا يوجد ملف مرفق"
    id_attachment_preview.short_description = "معاينة ملف الهوية"


# ---------- SitePlan ----------
class SitePlanOwnerInline(admin.TabularInline):
    model = SitePlanOwner
    extra = 0
    fields = ("owner_name_ar", "owner_name_en", "nationality", "phone", "id_number", "id_attachment", "share_percent")
    readonly_fields = ()

@admin.register(SitePlan)
class SitePlanAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "municipality", "zone", "sector", "land_no", "plot_area_sqm", "created_at")
    list_filter = ("municipality", "zone", "sector")
    search_fields = ("project__name", "land_no", "plot_address")
    inlines = [SitePlanOwnerInline]


# ---------- BuildingLicense ----------
@admin.register(BuildingLicense)
class BuildingLicenseAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "license_no", "license_type", "issue_date", "contractor_name", "created_at")
    list_filter = ("license_type", "city", "zone", "sector")
    search_fields = ("license_no", "project__name", "contractor_name", "consultant_name")


# ---------- Contract ----------
@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "contract_type", "contract_date", "total_project_value", "created_at")
    list_filter = ("contract_type",)
    search_fields = ("project__name", "tender_no", "contractor_name")


# ---------- Awarding ----------
@admin.register(Awarding)
class AwardingAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "award_date", "project_number", "created_at")
    search_fields = ("project__name", "project_number", "consultant_registration_number", "contractor_registration_number")


# ---------- Payment ----------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "amount", "date", "description", "created_at")
    list_filter = ("date", "project")
    search_fields = ("project__name", "description")
    date_hierarchy = "date"


# ---------- Consultant ----------
@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "name_en", "license_no", "phone", "email", "projects_count", "created_at")
    list_filter = ("tenant",)
    search_fields = ("name", "name_en", "license_no", "phone", "email")
    readonly_fields = ("created_at", "updated_at", "image_preview")
    fieldsets = (
        ("معلومات أساسية", {
            "fields": (
                "tenant",
                "name",
                "name_en",
                "license_no",
            )
        }),
        ("معلومات الاتصال", {
            "fields": (
                "phone",
                "email",
                "address",
            )
        }),
        ("صورة الاستشاري", {
            "fields": (
                "image",
                "image_preview",
            )
        }),
        ("ملاحظات", {
            "fields": ("notes",)
        }),
        ("معلومات إضافية", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )
    
    def image_preview(self, obj):
        """معاينة صورة الاستشاري"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border: 1px solid #ddd; padding: 5px; border-radius: 8px;" />',
                obj.image.url
            )
        return "لا توجد صورة"
    image_preview.short_description = "معاينة الصورة"
    
    def projects_count(self, obj):
        """عدد المشاريع المرتبطة"""
        return obj.projects.count()
    projects_count.short_description = "عدد المشاريع"


# ---------- ProjectConsultant ----------
@admin.register(ProjectConsultant)
class ProjectConsultantAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "consultant", "role", "created_at")
    list_filter = ("role", "consultant__tenant")
    search_fields = ("project__name", "consultant__name", "consultant__name_en")
