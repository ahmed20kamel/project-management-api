from pathlib import Path
import os

# ✅ تحميل .env فقط في التطوير
if os.getenv("ENVIRONMENT") != "production":
    from dotenv import load_dotenv
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# Security
# =========================
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise Exception("SECRET_KEY is missing")

DEBUG = os.getenv("DEBUG") == "True"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "eng-hayder.onrender.com",            # Backend على Render
    "eng-hayder-frontend.onrender.com",   # Frontend على Render
]

# =========================
# Installed Apps
# =========================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_ratelimit",  # ✅ Rate limiting

    "projects.apps.ProjectsConfig",  # ✅ استخدام AppConfig للتأكد من تحميل signals
    "authentication.apps.AuthenticationConfig",  # Authentication app
]

# =========================
# Middleware (الترتيب مهم)
# =========================
MIDDLEWARE = [
    # لازم يكون أول واحد
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    # ✅ استخدام custom CSRF middleware لدعم Partitioned attribute
    "backend.csrf_middleware.CustomCsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "authentication.middleware.TenantMiddleware",  # Multi-Tenant Middleware
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =========================
# URLs / WSGI / ASGI
# =========================
ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"

# =========================
# Templates
# =========================
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

# =========================
# Database
# =========================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
        "CONN_MAX_AGE": 600,  # Connection pooling: 10 minutes
    }
}

# =========================
# Cache Configuration
# =========================
REDIS_URL = os.getenv("REDIS_URL", None)

if REDIS_URL:
    # ✅ استخدام Redis إذا كان متاحاً
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PARSER_CLASS": "redis.connection.HiredisParser",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": 50,
                    "retry_on_timeout": True,
                },
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                "IGNORE_EXCEPTIONS": True,  # لا نرفع استثناء إذا فشل cache
            },
            "KEY_PREFIX": "project_mgmt",
            "TIMEOUT": 300,  # 5 minutes default
        }
    }
else:
    # ✅ استخدام memory cache كبديل إذا لم يكن Redis متاحاً
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
            "TIMEOUT": 300,
        }
    }


# =========================
# CORS / CSRF
# =========================
CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    # تطوير: اسمح لكل الأصول (المكتبة هترد بـ Origin الفعلي مش *)
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
else:
    # إنتاج: اسمح فقط لواجهة Render
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [
        "https://eng-hayder-frontend.onrender.com",
    ]

# صرّح بالمناهج والهيدرز للـ preflight
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-csrf-token",  # ✅ دعم كلا الاسمين
    "x-requested-with",
]
# ✅ إضافة CORS expose headers للسماح للـ frontend بقراءة headers
CORS_EXPOSE_HEADERS = [
    "content-type",
    "x-csrftoken",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://eng-hayder-frontend.onrender.com",
]

# سياسة الكوكيز حسب البيئة
if DEBUG:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_HTTPONLY = False  # ✅ للسماح للـ JavaScript بالوصول في التطوير
else:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"  # ✅ مطلوب للـ cross-domain
    SESSION_COOKIE_SAMESITE = "None"  # ✅ مطلوب للـ cross-domain
    CSRF_COOKIE_HTTPONLY = False  # ✅ للسماح للـ JavaScript بالوصول
    # ✅ لا نضيف CSRF_COOKIE_DOMAIN لأننا نريد أن يعمل على جميع subdomains
    # ✅ إضافة Partitioned attribute للـ CSRF cookie (لحل تحذير Chrome)
    # Note: Django لا يدعم Partitioned مباشرة، لكن يمكن إضافته عبر middleware

# =========================
# Security Headers (Production Only)
# =========================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

# =========================
# Static / Media
# =========================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = "/var/data/uploads"

os.makedirs(MEDIA_ROOT, exist_ok=True)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# Django REST Framework
# =========================
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "backend.exceptions.custom_exception_handler",
    # ✅ تعطيل CSRF protection للـ DRF views (نستخدم JWT)
    # Note: DRF views لا تحتاج CSRF protection لأنها تستخدم JWT authentication
    # لكن Django CSRF middleware قد يسبب مشاكل، لذلك نتعامل معها في exception handler
}

# =========================
# JWT Settings
# =========================
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# =========================
# Custom User Model
# =========================
AUTH_USER_MODEL = "authentication.User"

# =========================
# Logging
# =========================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if not DEBUG else "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO" if not DEBUG else "DEBUG",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR" if not DEBUG else "WARNING",
            "propagate": False,
        },
        "projects": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "projects.views": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "projects.serializers": {
            "handlers": ["console"],
            "level": "WARNING" if not DEBUG else "INFO",
            "propagate": False,
        },
        "authentication": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
