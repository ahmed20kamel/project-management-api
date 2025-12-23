# backend/backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.generic import RedirectView
from projects.views import csrf_ping  # يستورد csrf endpoint
import os

# =======================
# تحويل الجذر حسب البيئة
# =======================
# مثال على Render:
# FRONTEND_URL=https://eng-hayder-frontend.onrender.com/
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()

def healthz(_):
    return JsonResponse({"status": "ok"})

urlpatterns = []

# التعامل مع الجذر /
if FRONTEND_URL:
    # يحوّل الجذر للواجهة في الإنتاج
    urlpatterns.append(path("", RedirectView.as_view(url=FRONTEND_URL, permanent=False)))
else:
    # في المحلي: يرجّع JSON بسيط بدل 404
    urlpatterns.append(path("", lambda r: JsonResponse({"detail": "backend ok", "set_FRONTEND_URL_to_redirect": True})))

# باقي المسارات
urlpatterns += [
    path("healthz/", healthz),
    path("admin/", admin.site.urls),
    path("api/csrf/", csrf_ping),       # يزرع كوكي CSRF
    path("api/public/", include("authentication.public_urls")),  # Public APIs
    path("api/auth/", include("authentication.urls")),  # Authentication APIs
    path("api/", include("projects.urls")),  # باقي الـ API
]

# =======================
# خدمة ملفات الـ Media في التطوير
# =======================
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
