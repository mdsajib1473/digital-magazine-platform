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
