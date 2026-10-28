"""
URL configuration for echoMoments project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseNotFound

admin.site.site_header = "EchoMoments Admin"
admin.site.site_title = "EchoMoments Admin Portal" 
admin.site.site_index_title = " Welcome to EchoMoments"


def block_legacy_public_event_photos(request, filename):
    return HttpResponseNotFound()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('home.urls')),
    path("accounts/", include("accounts.urls")), # ✅ link accounts
    path('events/', include('events.urls')),  # events app routes
    path("accounts/", include("django.contrib.auth.urls")),  # 🔹 yeh add karo



]

from django.conf import settings
from django.conf.urls.static import static

media_prefix = settings.MEDIA_URL.lstrip("/").rstrip("/")
for private_media_dir in ("event_photos", "event_covers", "profile_pics"):
    urlpatterns += [path(f"{media_prefix}/{private_media_dir}/<path:filename>", block_legacy_public_event_photos)]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
