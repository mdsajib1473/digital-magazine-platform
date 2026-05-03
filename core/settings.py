"""
Django settings for the Unmad Digital Archive (core project).

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/
"""

from pathlib import Path

from decouple import Csv, config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-x8n0o+1m$i4%_3%4be4ahat=5*i!@kei+qfzj7cwuea7$%pa6t",
)
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost",
    cast=Csv(),
)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    # jazzmin MUST come before django.contrib.admin so it can override the
    # admin templates. Listed in DJANGO_APPS rather than THIRD_PARTY_APPS so
    # the ordering invariant is unmissable when reading this file top-to-bottom.
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "tailwind",
    "theme",
    "django_browser_reload",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.magazines",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # django-browser-reload must come after every middleware that produces
    # responses (so it can inject the reload script).
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
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
    },
]


# ---------------------------------------------------------------------------
# Database (SQLite locally; switch to Postgres in production via env vars)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# ---------------------------------------------------------------------------
# Email
#
# Local dev: print emails (including password-reset links) to the runserver
# console. To switch to a real SMTP backend in production, override EMAIL_BACKEND
# via .env to 'django.core.mail.backends.smtp.EmailBackend' and configure
# EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD / EMAIL_USE_TLS.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default="Unmad Archive <no-reply@unmadbd.com>",
)


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# ---------------------------------------------------------------------------
# Storage (Supabase S3-compatible, with local FS fallback)
#
# Toggle USE_SUPABASE_STORAGE=True in your .env once both buckets exist on
# Supabase. Until then, all uploads land in /media/ via the dev server.
# ---------------------------------------------------------------------------
USE_SUPABASE_STORAGE = config("USE_SUPABASE_STORAGE", default=False, cast=bool)

if USE_SUPABASE_STORAGE:
    # Endpoint format: https://<project_ref>.storage.supabase.co/storage/v1/s3
    SUPABASE_S3_ENDPOINT_URL = config("SUPABASE_S3_ENDPOINT_URL")
    SUPABASE_S3_REGION = config("SUPABASE_S3_REGION", default="ap-southeast-1")
    SUPABASE_S3_ACCESS_KEY_ID = config("SUPABASE_S3_ACCESS_KEY_ID")
    SUPABASE_S3_SECRET_ACCESS_KEY = config("SUPABASE_S3_SECRET_ACCESS_KEY")
    SUPABASE_PUBLIC_BUCKET = config("SUPABASE_PUBLIC_BUCKET", default="unmad-archive")
    SUPABASE_PRIVATE_BUCKET = config(
        "SUPABASE_PRIVATE_BUCKET", default="unmad-archive-pdfs"
    )
    SUPABASE_SIGNED_URL_EXPIRE = config(
        "SUPABASE_SIGNED_URL_EXPIRE", default=3600, cast=int
    )

    # Shared S3 args -- Supabase requires path-style URLs and SigV4.
    _SUPABASE_S3_COMMON = {
        "endpoint_url": SUPABASE_S3_ENDPOINT_URL,
        "region_name": SUPABASE_S3_REGION,
        "access_key": SUPABASE_S3_ACCESS_KEY_ID,
        "secret_key": SUPABASE_S3_SECRET_ACCESS_KEY,
        "addressing_style": "path",
        "signature_version": "s3v4",
    }

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
        "public_media": {
            "BACKEND": "core.storages.PublicMediaStorage",
            "OPTIONS": {
                **_SUPABASE_S3_COMMON,
                "bucket_name": SUPABASE_PUBLIC_BUCKET,
            },
        },
        "private_media": {
            "BACKEND": "core.storages.PrivateMediaStorage",
            "OPTIONS": {
                **_SUPABASE_S3_COMMON,
                "bucket_name": SUPABASE_PRIVATE_BUCKET,
                "querystring_expire": SUPABASE_SIGNED_URL_EXPIRE,
            },
        },
    }
else:
    # Local development: every storage alias maps to the same /media/ folder.
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
        "public_media": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "private_media": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
    }


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Tailwind (django-tailwind)
# ---------------------------------------------------------------------------
TAILWIND_APP_NAME = "theme"

# Required for django-browser-reload to inject the live-reload script in DEBUG.
INTERNAL_IPS = ["127.0.0.1"]

# django-tailwind on Windows can't always resolve `npm.cmd` from PATH,
# so we point at it explicitly. On macOS/Linux this would be /usr/local/bin/npm.
NPM_BIN_PATH = r"C:\Program Files\nodejs\npm.cmd"


# ---------------------------------------------------------------------------
# django-jazzmin (modern admin UI)
# ---------------------------------------------------------------------------
JAZZMIN_SETTINGS = {
    # Branding shown across admin pages.
    "site_title": "Unmad Admin",
    "site_header": "Unmad Archive",
    "site_brand": "Unmad",
    "site_logo_classes": "img-circle",
    "welcome_sign": "Welcome to the Unmad Digital Archive admin",
    "copyright": "Unmad Digital Archive",
    # Global search bar at the top of the admin -- queries these models.
    "search_model": ["magazines.Issue", "accounts.CustomUser"],
    # Sidebar layout.
    "show_sidebar": True,
    "navigation_expanded": True,
    # Font Awesome icons (Jazzmin bundles FA free).
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-users",
        "accounts": "fas fa-id-card",
        "accounts.CustomUser": "fas fa-user",
        "magazines": "fas fa-book-open",
        "magazines.Category": "fas fa-folder-open",
        "magazines.Issue": "fas fa-book",
        "magazines.Purchase": "fas fa-receipt",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    # Custom ordering: domain models first, accounts next, Django plumbing last.
    "order_with_respect_to": [
        "magazines",
        "magazines.Issue",
        "magazines.Category",
        "magazines.Purchase",
        "accounts",
        "accounts.CustomUser",
        "auth",
    ],
    # Top bar links: a quick "View site" jump back to the public landing.
    "topmenu_links": [
        {"name": "View site", "url": "home", "new_window": True},
        {"model": "magazines.Issue"},
    ],
    # Hide the live theme picker in production -- exposes /jazzmin/ui-builder/.
    "show_ui_builder": False,
    # Sensible defaults for change-form layout.
    "changeform_format": "horizontal_tabs",
    "related_modal_active": True,
}

# Visual tweaks (AdminLTE / Bootstrap classes -- separate from Tailwind).
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-indigo",
    "accent": "accent-indigo",
    "navbar": "navbar-indigo navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-indigo",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    # Jazzmin 3.x: themes now support light/dark via data-bs-theme. The old
    # ``dark_mode_theme`` key is deprecated; ``default_theme_mode="auto"``
    # follows the user's OS preference.
    "default_theme_mode": "auto",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
