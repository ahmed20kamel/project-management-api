"""
Utility functions for project file storage management

This module provides a unified and organized file storage system for project attachments,
following best practices for project management systems.

Structure:
    media/
    └── projects/
        └── project_{project_code}_{owner_name_en}/
            ├── Project Info- معلومات المشروع/
            ├── contracts - العقود/
            ├── Project Schedule– المدة الزمنية للمشروع/
            ├── variation orders - والتعديلات أوامر التغيير/
            ├── variation orders Approved - المعتمدة أوامر التغيير/
            ├── invoices - الفواتير/
            └── payments - الدفعات/
"""
import os
import re
from django.core.files.storage import default_storage
from django.utils.text import slugify


# Project phases mapping
# المفاتيح: القيم المستخدمة في الكود
# القيم: أسماء المجلدات الفعلية في نظام الملفات
PROJECT_PHASES = {
    'project_info': 'Project Info- معلومات المشروع',
    'contracts': 'contracts - العقود',
    'project_schedule': 'Project Schedule– المدة الزمنية للمشروع',
    'variation_orders': 'variation orders - والتعديلات أوامر التغيير',
    'variation_orders_approved': 'variation orders Approved - المعتمدة أوامر التغيير',
    'invoices': 'invoices - الفواتير',
    'payments': 'payments - الدفعات',
    # Legacy phases for backward compatibility
    'siteplan': 'siteplan',
    'licensing': 'licensing',
    'awarding': 'awarding',
    'execution': 'execution',
    'owners': 'owners',
}


def sanitize_filename(filename):
    """
    تنظيف اسم الملف من الأحرف غير المسموحة
    
    Args:
        filename: اسم الملف الأصلي
    
    Returns:
        str: اسم ملف نظيف وآمن
    """
    # استخراج الامتداد
    name, ext = os.path.splitext(filename)
    
    # تنظيف الاسم من الأحرف غير المسموحة
    # السماح بالأحرف العربية والإنجليزية والأرقام والشرطة والشرطة السفلية والنقطة
    name = re.sub(r'[^\w\s\-_.\u0600-\u06FF]', '', name)
    
    # استبدال المسافات بشرطة سفلية
    name = name.replace(' ', '_')
    
    # إزالة الشرطات المتعددة
    name = re.sub(r'[-_]+', '_', name)
    
    return f"{name}{ext}" if ext else name


def clean_owner_name_en(owner_name_en):
    """
    تنظيف اسم المالك الإنجليزي للاستخدام في اسم المجلد
    
    - تحويل إلى lowercase
    - استبدال المسافات بشرطة سفلية
    - إزالة الأحرف العربية والأحرف الخاصة
    - السماح فقط بالأحرف الإنجليزية والأرقام والشرطة السفلية
    
    Args:
        owner_name_en: اسم المالك بالإنجليزي
    
    Returns:
        str: اسم نظيف (lowercase + underscore فقط)
    """
    if not owner_name_en or not isinstance(owner_name_en, str):
        return ""
    
    # تحويل إلى lowercase
    cleaned = owner_name_en.lower().strip()
    
    # إزالة الأحرف العربية والأحرف الخاصة - السماح فقط بالإنجليزية والأرقام والمسافات
    cleaned = re.sub(r'[^a-z0-9\s_]', '', cleaned)
    
    # استبدال المسافات بشرطة سفلية
    cleaned = cleaned.replace(' ', '_')
    
    # إزالة الشرطات السفلية المتعددة
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # إزالة الشرطات السفلية من البداية والنهاية
    cleaned = cleaned.strip('_')
    
    return cleaned


def get_project_folder_name(project):
    """
    الحصول على اسم مجلد المشروع
    
    يستخدم project_{project_code}_{owner_name_en}
    
    Args:
        project: كائن Project أو project_id
    
    Returns:
        str: اسم المجلد (project_{code}_{owner_en})
    """
    # إذا كان project_id فقط
    if isinstance(project, int):
        # نحتاج لجلب المشروع من قاعدة البيانات
        try:
            from .models import Project
            project = Project.objects.get(id=project)
        except (Project.DoesNotExist, ImportError):
            return f"project_{project}"
    
    if not hasattr(project, 'id') or not project.id:
        return "project_unknown"
    
    # الحصول على project_code (internal_code)
    project_code = getattr(project, 'internal_code', None)
    if not project_code or not project_code.strip():
        project_code = str(project.id)  # Fallback إلى ID إذا لم يكن هناك code
    
    # الحصول على owner_name_en من المالك المفوض (is_authorized=True)
    owner_name_en = ""
    try:
        # محاولة الحصول على SitePlan باستخدام query مباشر لتجنب مشاكل الـ caching
        from .models import SitePlan, SitePlanOwner
        try:
            siteplan = SitePlan.objects.get(project_id=project.id)
            if siteplan:
                # البحث عن المالك المفوض أولاً (is_authorized=True)
                authorized_owner = SitePlanOwner.objects.filter(
                    siteplan=siteplan, 
                    is_authorized=True
                ).first()
                if authorized_owner:
                    owner_name_en = getattr(authorized_owner, 'owner_name_en', '') or ''
                else:
                    # إذا لم يكن هناك مالك مفوض، نستخدم الأول
                    first_owner = SitePlanOwner.objects.filter(
                        siteplan=siteplan
                    ).order_by('id').first()
                    if first_owner:
                        owner_name_en = getattr(first_owner, 'owner_name_en', '') or ''
        except SitePlan.DoesNotExist:
            # لا يوجد siteplan - هذا طبيعي للمشاريع الجديدة
            pass
        except Exception as e:
            # في حالة أي خطأ آخر، نستخدم fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error getting owner_name_en for project {project.id}: {e}")
    except Exception:
        pass
    
    # تنظيف owner_name_en
    cleaned_owner_name = clean_owner_name_en(owner_name_en) if owner_name_en else ""
    
    # بناء اسم المجلد
    if cleaned_owner_name:
        return f"project_{project_code}_{cleaned_owner_name}"
    else:
        # إذا لم يكن هناك owner_name_en، نستخدم code فقط
        return f"project_{project_code}"


def get_project_file_path(project, phase, filename, subfolder=None):
    """
    إنشاء مسار موحد لحفظ ملفات المشروع
    
    Args:
        project: كائن Project أو project_id
        phase: مرحلة المشروع (siteplan, licensing, contracts, etc.)
        filename: اسم الملف
        subfolder: مجلد فرعي داخل المرحلة (اختياري)
    
    Returns:
        str: المسار الكامل للملف
    
    Examples:
        >>> get_project_file_path(project, 'contracts', 'contract.pdf')
        'projects/project_123_my_project/contracts - العقود/contract.pdf'
        
        >>> get_project_file_path(project, 'contracts', 'drawing.pdf', 'drawings')
        'projects/project_123_my_project/contracts - العقود/drawings/drawing.pdf'
        
        >>> get_project_file_path(project, 'project_info', 'site_plan.pdf')
        'projects/project_123_my_project/Project Info- معلومات المشروع/site_plan.pdf'
    """
    # الحصول على اسم مجلد المشروع
    project_folder = get_project_folder_name(project)
    
    # الحصول على اسم المجلد الفعلي من PROJECT_PHASES
    # إذا كانت phase موجودة في المفاتيح، نستخدم القيمة (اسم المجلد الفعلي)
    # وإلا نستخدم phase كما هي (للتوافق مع البيانات القديمة)
    actual_folder_name = PROJECT_PHASES.get(phase, phase)
    
    # التحقق من صحة المرحلة (إذا لم تكن موجودة في المفاتيح أو القيم)
    if phase not in PROJECT_PHASES and phase not in PROJECT_PHASES.values():
        # السماح بالمراحل القديمة للتوافق
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Phase '{phase}' not found in PROJECT_PHASES, using as-is for backward compatibility")
    
    # ✅ استخراج اسم الملف فقط إذا كان filename يحتوي على مسار كامل (للويندوز)
    # Django على Windows قد يمرر filename مع \ أو / أو مسار كامل
    if filename:
        # تحويل \ إلى / أولاً للتأكد من التوافق
        filename = filename.replace('\\', '/')
        # استخراج اسم الملف فقط (آخر جزء بعد /)
        # استخدام split('/') للحصول على آخر جزء (يعمل حتى مع backslash)
        filename = filename.split('/')[-1] if '/' in filename else filename
        # استخدام os.path.basename أيضاً للتأكد (للتعامل مع edge cases)
        filename = os.path.basename(filename)
    
    # تنظيف اسم الملف
    clean_filename = sanitize_filename(filename)
    
    # بناء المسار باستخدام اسم المجلد الفعلي
    path_parts = ['projects', project_folder, actual_folder_name]
    
    # إضافة المجلد الفرعي إذا كان موجوداً
    if subfolder:
        # تقسيم subfolder على '/' لمعالجة المسارات المتعددة المستويات
        subfolder_parts = subfolder.split('/')
        # تنظيف كل جزء من أجزاء المجلد الفرعي
        for part in subfolder_parts:
            if part:  # تجاهل الأجزاء الفارغة
                clean_part = re.sub(r'[^\w\s\-_.]', '', part)
                clean_part = clean_part.replace(' ', '_')
                clean_part = re.sub(r'[-_]+', '_', clean_part)
                clean_part = clean_part.strip('_')
                if clean_part:  # إضافة الجزء فقط إذا لم يكن فارغاً بعد التنظيف
                    path_parts.append(clean_part)
    
    # إضافة اسم الملف
    path_parts.append(clean_filename)
    
    # دمج المسار مع ضمان استخدام '/' دائماً (مهم لـ Windows)
    file_path = '/'.join(path_parts)
    
    # ✅ التأكد من تحويل أي backslash متبقية إلى forward slash (للويندوز)
    file_path = file_path.replace('\\', '/')
    
    return file_path


def save_project_file(file_obj, project, phase, filename=None, subfolder=None, overwrite=False):
    """
    حفظ ملف في المسار المنظم للمشروع
    
    Args:
        file_obj: ملف Django (InMemoryUploadedFile أو UploadedFile)
        project: كائن Project أو project_id
        phase: مرحلة المشروع
        filename: اسم الملف (اختياري، سيستخدم اسم الملف الأصلي إذا لم يُحدد)
        subfolder: مجلد فرعي داخل المرحلة (اختياري)
        overwrite: إذا كان True، يحذف الملف القديم بنفس الاسم قبل الحفظ (لتجنب suffix عشوائي)
    
    Returns:
        str: المسار المحفوظ للملف
    
    Examples:
        >>> save_project_file(file, project, 'contracts', 'contract.pdf')
        'projects/project_123_my_project/contracts - العقود/contract.pdf'
    """
    # استخدام اسم الملف المحدد أو اسم الملف الأصلي
    if not filename:
        filename = file_obj.name if hasattr(file_obj, 'name') else 'file'
    
    # الحصول على المسار
    file_path = get_project_file_path(project, phase, filename, subfolder)
    
    # ✅ إذا كان overwrite=True، نحذف الملف القديم أولاً لتجنب suffix عشوائي
    if overwrite and default_storage.exists(file_path):
        try:
            default_storage.delete(file_path)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not delete existing file {file_path}: {e}")
    
    # حفظ الملف
    saved_path = default_storage.save(file_path, file_obj)
    
    return saved_path


def get_project_phase_from_model(model_instance):
    """
    تحديد مرحلة المشروع من نوع النموذج
    
    Args:
        model_instance: كائن من أحد نماذج المشروع
    
    Returns:
        str: اسم المرحلة
    """
    model_name = model_instance.__class__.__name__.lower()
    
    phase_mapping = {
        'siteplan': 'siteplan',
        'buildinglicense': 'licensing',
        'contract': 'contracts',
        'awarding': 'awarding',
        'startorder': 'execution',
        'variation': 'execution',
        'payment': 'payments',
        'siteplanowner': 'owners',
    }
    
    return phase_mapping.get(model_name, 'execution')


def get_next_numbered_subfolder(project, phase, base_folder_name):
    """
    حساب رقم المجلد الفرعي التالي للملاحق أو التوضيحات المرقمة
    
    Args:
        project: كائن Project أو project_id
        phase: مرحلة المشروع (مثل 'contracts')
        base_folder_name: اسم المجلد الأساسي (مثل 'ملحق عقد' أو 'توضيحات تعاقدية')
    
    Returns:
        str: رقم المجلد التالي بصيغة "01", "02", إلخ
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        project_folder = get_project_folder_name(project)
        actual_folder_name = PROJECT_PHASES.get(phase, phase)
        
        # البحث عن جميع المجلدات الموجودة التي تبدأ بـ base_folder_name
        base_path = f'projects/{project_folder}/{actual_folder_name}'
        
        # الحصول على قائمة الملفات والمجلدات الموجودة
        if not default_storage.exists(base_path):
            return "01"
        
        # البحث عن المجلدات المرقمة
        max_number = 0
        try:
            # محاولة قراءة محتويات المجلد
            # Django storage لا يدعم listdir مباشرة، لذلك نستخدم طريقة أخرى
            from django.conf import settings
            import os
            
            full_path = os.path.join(settings.MEDIA_ROOT, base_path)
            if os.path.exists(full_path) and os.path.isdir(full_path):
                for item in os.listdir(full_path):
                    if os.path.isdir(os.path.join(full_path, item)):
                        # البحث عن رقم في اسم المجلد
                        import re
                        match = re.search(r'(\d+)', item)
                        if match:
                            number = int(match.group(1))
                            if number > max_number:
                                max_number = number
        except Exception as e:
            logger.debug(f"Could not list directory {base_path}: {e}")
            # في حالة الخطأ، نبدأ من 01
            return "01"
        
        # إرجاع الرقم التالي بصيغة "01", "02", إلخ
        next_number = max_number + 1
        return f"{next_number:02d}"
        
    except Exception as e:
        logger.warning(f"Error calculating next numbered subfolder: {e}")
        return "01"


def get_project_from_instance(instance):
    """
    استخراج المشروع من أي كائن مرتبط به
    
    Args:
        instance: كائن مرتبط بمشروع
    
    Returns:
        Project: كائن المشروع أو None
    """
    # إذا كان الكائن نفسه مشروع
    if hasattr(instance, '_meta') and instance._meta.model_name == 'project':
        return instance
    
    # البحث عن حقل project
    if hasattr(instance, 'project'):
        return instance.project
    
    # البحث عن siteplan ثم project
    if hasattr(instance, 'siteplan') and hasattr(instance.siteplan, 'project'):
        return instance.siteplan.project
    
    return None


def create_project_folder_structure(project):
    """
    إنشاء هيكل المجلدات الكامل للمشروع تلقائياً
    
    يتم إنشاء جميع المجلدات المطلوبة حتى لو كانت فارغة في البداية.
    هذا يضمن توحيد تنظيم جميع المشاريع من اليوم الأول.
    
    Args:
        project: كائن Project أو project_id
    
    Returns:
        bool: True إذا تم إنشاء الهيكل بنجاح، False في حالة الخطأ
    
    Structure:
        projects/
        └── project_{code}_{owner_en}/
            ├── Project Info- معلومات المشروع/
            │   ├── مخطط الأرض - Site Plan/
            │   ├── هوية المالك - Owner ID/
            │   ├── هوية المفوض - Authorized Owner ID/
            │   ├── رخصة البناء - Building Permit/
            │   └── كتاب ترسية البنك – Bank Awarding Letter/
            ├── contracts - العقود/
            ├── Project Schedule– المدة الزمنية للمشروع/
            ├── variation orders - والتعديلات أوامر التغيير/
            ├── variation orders Approved - المعتمدة أوامر التغيير/
            ├── invoices - الفواتير/
            └── payments - الدفعات/
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # الحصول على اسم مجلد المشروع
        project_folder = get_project_folder_name(project)
        
        # التحقق من وجود مجلد قديم للمشروع (project_{code} فقط) وننقل الملفات منه إذا كان موجوداً
        if not isinstance(project, int) and hasattr(project, 'id') and project.id:
            project_code = getattr(project, 'internal_code', None)
            if not project_code or not project_code.strip():
                project_code = str(project.id)
            
            old_folder_name = f"project_{project_code}"
            old_folder_path = f'projects/{old_folder_name}'
            new_folder_path = f'projects/{project_folder}'
            
            # إذا كان هناك مجلد قديم (project_{code} فقط) والمجلد الجديد مختلف
            if project_folder != old_folder_name and default_storage.exists(old_folder_path):
                if not default_storage.exists(new_folder_path):
                    # نقل الملفات من المجلد القديم إلى الجديد
                    try:
                        import shutil
                        from django.conf import settings
                        
                        old_full_path = os.path.join(settings.MEDIA_ROOT, old_folder_path)
                        new_full_path = os.path.join(settings.MEDIA_ROOT, new_folder_path)
                        
                        if os.path.exists(old_full_path) and os.path.isdir(old_full_path):
                            # إنشاء المجلد الجديد
                            os.makedirs(new_full_path, exist_ok=True)
                            # نقل جميع الملفات
                            for item in os.listdir(old_full_path):
                                src = os.path.join(old_full_path, item)
                                dst = os.path.join(new_full_path, item)
                                if os.path.isdir(src):
                                    if os.path.exists(dst):
                                        shutil.rmtree(dst)
                                    shutil.copytree(src, dst)
                                else:
                                    shutil.copy2(src, dst)
                            # حذف المجلد القديم بعد النقل
                            shutil.rmtree(old_full_path)
                            logger.info(f"📁 Moved files from {old_folder_name} to {project_folder} for project {project.id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not move old folder {old_folder_name} to {project_folder}: {e}")
                        # في حالة الفشل، نستخدم المجلد القديم
                        project_folder = old_folder_name
                else:
                    # المجلد الجديد موجود بالفعل - نستخدمه
                    logger.debug(f"📁 Using existing folder {project_folder}")
        
        logger.info(f"📁 Creating folder structure for project: {project_folder}")
        
        # تعريف هيكل المجلدات الكامل (حسب الهيكل المقترح)
        folder_structure = [
            # Project Info- معلومات المشروع (جميع الملفات مباشرة بدون subfolders)
            f'projects/{project_folder}/Project Info- معلومات المشروع',
            
            # contracts - العقود (جميع الملفات مباشرة + مجلد المخططات فقط)
            f'projects/{project_folder}/contracts - العقود',
            f'projects/{project_folder}/contracts - العقود/مخططات_العقد',
            
            # Project Schedule– المدة الزمنية للمشروع
            f'projects/{project_folder}/Project Schedule– المدة الزمنية للمشروع',
            
            # variation orders - والتعديلات أوامر التغيير
            f'projects/{project_folder}/variation orders - والتعديلات أوامر التغيير',
            
            # variation orders Approved - المعتمدة أوامر التغيير
            f'projects/{project_folder}/variation orders Approved - المعتمدة أوامر التغيير',
            
            # invoices - الفواتير
            f'projects/{project_folder}/invoices - الفواتير',
            
            # payments - الدفعات
            f'projects/{project_folder}/payments - الدفعات',
        ]
        
        # إنشاء جميع المجلدات
        created_folders = []
        for folder_path in folder_structure:
            try:
                # إنشاء ملف .gitkeep فارغ لضمان إنشاء المجلد حتى لو كان فارغاً
                # Django storage لا ينشئ مجلدات فارغة، لذلك ننشئ ملف مؤقت
                keep_file_path = f'{folder_path}/.gitkeep'
                
                # التحقق من وجود المجلد بالفعل
                if not default_storage.exists(keep_file_path):
                    # إنشاء ملف فارغ (ContentFile) لضمان إنشاء المجلد
                    from django.core.files.base import ContentFile
                    empty_file = ContentFile('')
                    default_storage.save(keep_file_path, empty_file)
                    created_folders.append(folder_path)
                    logger.debug(f"✅ Created folder structure: {folder_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not create folder {folder_path}: {e}")
                # نكمل إنشاء باقي المجلدات حتى لو فشل أحدها
        
        if created_folders:
            logger.info(f"✅ Created folder structure for project {project_folder}: {len(created_folders)} folders")
        else:
            logger.debug(f"📁 Folder structure already exists for project {project_folder}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating folder structure for project: {e}", exc_info=True)
        return False

