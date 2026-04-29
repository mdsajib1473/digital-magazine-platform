"""URL configuration for the Unmad Digital Archive (core project)."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth URLs (signup, login, logout, password reset/change).
    path("accounts/", include("apps.accounts.urls")),
    # Magazines app owns the site root (landing page = issue list, name="home").
    path("", include("apps.magazines.urls")),
]

if settings.DEBUG:
    # Live-reload the browser when templates / CSS change (django-browser-reload).
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
    # Serve user-uploaded media via Django dev server (production uses Supabase).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
