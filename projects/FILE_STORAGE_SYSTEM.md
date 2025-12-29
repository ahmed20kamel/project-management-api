# نظام حفظ الملفات الموحد للمشاريع

## نظرة عامة

تم تنفيذ نظام موحد ومنظم لحفظ مرفقات المشاريع، يتبع أفضل الممارسات في أنظمة إدارة المشاريع.

## الهيكل التنظيمي

يتم حفظ جميع ملفات المشاريع في الهيكل التالي. **يتم إنشاء هذا الهيكل تلقائياً لكل مشروع جديد** حتى لو كانت المجلدات فارغة:

```
media/
└── projects/
    └── project_{project_id}_{project_name}/
        ├── Project Info- معلومات المشروع/    # Project Info- معلومات المشروع
        │   ├── مخطط الأرض - Site Plan/        # مخطط الأرض - Site Plan
        │   ├── هوية المالك - Owner ID/        # هوية المالك - Owner ID
        │   ├── هوية المفوض - Authorized Owner ID/  # هوية المفوض - Authorized Owner ID
        │   ├── رخصة البناء - Building Permit/ # رخصة البناء - Building Permit
        │   └── كتاب ترسية البنك – Bank Awarding Letter/  # كتاب ترسية البنك – Bank Awarding Letter
        │
        ├── contracts - العقود/                # contracts - العقود (مجلد واحد - كل الملفات داخله مباشرة)
        │   ├── العقد_الأصيل.pdf
        │   ├── ملحق_عقد_01.pdf
        │   ├── ملحق_عقد_02.pdf
        │   ├── توضيحات_تعاقدية_01.pdf
        │   ├── توضيحات_تعاقدية_02.pdf
        │   ├── عرض_السعر.pdf
        │   ├── ملحق_اتفاق_موقع.pdf
        │   ├── عقد_البنك.pdf
        │   ├── جدول_الكميات.pdf
        │   ├── جدول_المواد_المعتمدة.pdf
        │   ├── مخططات_MEP.pdf
        │   ├── المخططات_المعمارية.pdf
        │   ├── المخططات_الإنشائية.pdf
        │   ├── مخططات_الديكور.pdf
        │   └── المواصفات_العامة_والخاصة.pdf
        │
        ├── Project Schedule– المدة الزمنية للمشروع/  # Project Schedule– المدة الزمنية للمشروع
        │   ├── Excavation Notice - اشعار بدء الحفر
        │   ├── Notice to Proceed (NTP)أمر المباشرة
        │   ├── تمديد زمني 01 – Time Extension 01
        │   ├── تمديد زمني 02 - Time-Extension 02
        │   ├── الجدول الزمني المعتمد - Approved Project Schedule
        │   └── الجدول الزمني المحدث 01  - Updated-Project-Schedule Rev 01
        │
        ├── variation orders - والتعديلات أوامر التغيير/  # variation orders - والتعديلات أوامر التغيير
        │   ├── تغيير سعري 01 - Variation 01
        │   ├── تغيير سعري معدل 01 - Variation Rv 01
        │   └── تغيير سعري 02 - Variation 02
        │
        ├── variation orders Approved - المعتمدة أوامر التغيير/  # variation orders Approved - المعتمدة أوامر التغيير
        │   ├── تغيير سعري معدل 01 - Variation Rv 01
        │   └── تغيير سعري 02 - Variation 02
        │
        ├── invoices - الفواتير/              # invoices - الفواتير
        │   ├── فاتورة 001 - Invoice 001
        │   └── فاتورة 002 - Invoice 002
        │
        └── payments - الدفعات/               # payments - الدفعات
            ├── دفعة 001 -Payment 001
            └── دفعة 002 - Payment 002
```

## المراحل (Phases)

النظام يدعم المراحل التالية:

- `Project Info- معلومات المشروع`: معلومات المشروع (مخطط الأرض، هوية المالك، هوية المفوض، رخصة البناء، كتاب ترسية البنك)
- `contracts - العقود`: العقود (العقد الأصيل، الملاحق، التوضيحات، عقد البنك، جدول الكميات، جدول المواد، عرض السعر، المخططات، المواصفات)
- `Project Schedule– المدة الزمنية للمشروع`: المدة الزمنية للمشروع (اشعار بدء الحفر، أمر المباشرة، التمديدات الزمنية، الجداول الزمنية)
- `variation orders - والتعديلات أوامر التغيير`: أوامر التغيير والتعديلات
- `variation orders Approved - المعتمدة أوامر التغيير`: أوامر التغيير المعتمدة
- `invoices - الفواتير`: الفواتير
- `payments - الدفعات`: الدفعات

### المراحل القديمة (للتوافق مع البيانات القديمة):

- `siteplan`: مخطط الأرض
- `licensing`: التراخيص
- `awarding`: الترسية
- `execution`: التنفيذ (أوامر المباشرة، التعديلات)
- `owners`: الملاك (بطاقات الهوية)

## الاستخدام

### في Models (upload_to)

```python
from .utils import get_project_file_path, get_project_from_instance

def get_contract_file_path(instance, filename):
    """حفظ ملف العقد في المسار المنظم للمشروع."""
    project = get_project_from_instance(instance)
    if project:
        return get_project_file_path(project, 'contracts', filename, subfolder='main')
    return f"contracts/main/{filename}"  # Fallback للتوافق

contract_file = models.FileField(upload_to=get_contract_file_path, null=True, blank=True)
```

### في Serializers (حفظ يدوي)

```python
from .utils import save_project_file

# حفظ ملف مرفق
file_path = save_project_file(
    file_obj,
    project,
    'contracts',
    filename=file_obj.name,
    subfolder='attachments'
)
```

### الدوال المساعدة

#### `get_project_file_path(project, phase, filename, subfolder=None)`

إنشاء مسار موحد لحفظ ملفات المشروع.

**Parameters:**
- `project`: كائن Project أو project_id
- `phase`: مرحلة المشروع (siteplan, licensing, contracts, etc.)
- `filename`: اسم الملف
- `subfolder`: مجلد فرعي داخل المرحلة (اختياري)

**Returns:**
- `str`: المسار الكامل للملف

**Example:**
```python
path = get_project_file_path(project, 'contracts', 'contract.pdf', subfolder='main')
# Returns: 'projects/project_123_my_project/contracts/main/contract.pdf'
```

#### `save_project_file(file_obj, project, phase, filename=None, subfolder=None)`

حفظ ملف في المسار المنظم للمشروع.

**Parameters:**
- `file_obj`: ملف Django (InMemoryUploadedFile أو UploadedFile)
- `project`: كائن Project أو project_id
- `phase`: مرحلة المشروع
- `filename`: اسم الملف (اختياري، سيستخدم اسم الملف الأصلي إذا لم يُحدد)
- `subfolder`: مجلد فرعي داخل المرحلة (اختياري)

**Returns:**
- `str`: المسار المحفوظ للملف

#### `get_project_from_instance(instance)`

استخراج المشروع من أي كائن مرتبط به.

**Parameters:**
- `instance`: كائن مرتبط بمشروع

**Returns:**
- `Project`: كائن المشروع أو None

## الإنشاء التلقائي للهيكل

**عند إنشاء أي مشروع جديد في النظام، يتم إنشاء هيكل المجلدات الكامل تلقائياً** حتى لو كانت المجلدات فارغة في البداية. هذا يتم عبر Django signals (`post_save` signal للمشروع).

### المزايا

1. **تنظيم موحد**: كل مشروع له نفس الهيكل من اليوم الأول
2. **جاهزية فورية**: الهيكل موجود وجاهز قبل رفع أي ملفات
3. **منع العشوائية**: منع خلط ملفات مشاريع أو مراحل مختلفة
4. **سهولة الصيانة**: يمكن نسخ، نقل، أو حذف مشروع كامل بسهولة
5. **قابلية التوسع**: سهل إضافة مراحل أو مجلدات فرعية جديدة
6. **التوافق مع البيانات القديمة**: النظام يدعم الملفات القديمة مع fallback paths

## التوافق مع البيانات القديمة

النظام يدعم الملفات القديمة المحفوظة في المسارات القديمة. عند حفظ ملف جديد، سيتم حفظه في المسار الجديد المنظم، بينما الملفات القديمة تبقى في أماكنها الأصلية.

## ملاحظات

- أسماء المجلدات والملفات يتم تنظيفها تلقائياً من الأحرف غير المسموحة
- أسماء المشاريع الطويلة يتم تقصيرها لتجنب مشاكل المسارات الطويلة
- النظام يستخدم `slugify` لتنظيف أسماء المشاريع

