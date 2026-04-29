"""
S3-compatible storage backends for Supabase Storage.

We split media into two buckets to honour the access-control split:

* PublicMediaStorage  -> cover images, served via plain public URLs.
* PrivateMediaStorage -> PDFs, served via short-lived signed URLs.

The actual bucket names, endpoint, and credentials are injected via the
STORAGES dict in settings.py (so credentials never live in source).

Local development (USE_SUPABASE_STORAGE=False) bypasses these classes
entirely and uses django.core.files.storage.FileSystemStorage instead.
"""
from __future__ import annotations

from django.core.files.storage import storages
from storages.backends.s3 import S3Storage


class PublicMediaStorage(S3Storage):
    """Public bucket: cover images.

    - default_acl='public-read' is forwarded for S3-compatible providers
      that honour it (Supabase enforces bucket-level public, but we keep
      this for portability with real AWS S3 buckets later).
    - querystring_auth=False -> .url returns a plain, cacheable URL.
    - file_overwrite=False -> never silently clobber an existing file.
    """

    default_acl = "public-read"
    querystring_auth = False
    file_overwrite = False


class PrivateMediaStorage(S3Storage):
    """Private bucket: PDF files.

    - default_acl='private' keeps objects unreadable without a signature.
    - querystring_auth=True -> .url generates a signed URL.
    - querystring_expire is set per-storage in settings (STORAGES OPTIONS).
    """

    default_acl = "private"
    querystring_auth = True
    file_overwrite = False


# ---------------------------------------------------------------------------
# Storage callables for FileField/ImageField(storage=...)
#
# We use callables (not instances) so the migration framework only records an
# import path, and the *actual* backend is resolved at runtime from the
# STORAGES dict. This lets the same model field point at FileSystemStorage in
# local dev and at the S3 backend in production with zero code changes.
# ---------------------------------------------------------------------------


def public_media_storage():
    """Storage for cover images (public bucket in prod, /media/ locally)."""
    return storages["public_media"]


def private_media_storage():
    """Storage for PDFs (private bucket + signed URLs in prod, /media/ locally)."""
    return storages["private_media"]
