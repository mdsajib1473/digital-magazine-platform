"""
Direct boto3 probe against Supabase Storage. Bypasses django-storages so we
can see whether the credentials + endpoint + bucket names actually agree
with what exists on the Supabase project.

Run from project root:
    & .\venv\Scripts\python.exe _supabase_bucket_check.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from django.conf import settings


def mask(value: str, keep: int = 4) -> str:
    """Show only the first `keep` chars of a secret-ish value."""
    if not value:
        return "(empty)"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


def main() -> int:
    if not settings.USE_SUPABASE_STORAGE:
        print("USE_SUPABASE_STORAGE is False -- enable it in .env first.")
        return 1

    endpoint = settings.SUPABASE_S3_ENDPOINT_URL
    region = settings.SUPABASE_S3_REGION
    access_key = settings.SUPABASE_S3_ACCESS_KEY_ID
    secret_key = settings.SUPABASE_S3_SECRET_ACCESS_KEY
    public_bucket = settings.SUPABASE_PUBLIC_BUCKET
    private_bucket = settings.SUPABASE_PRIVATE_BUCKET

    print("=" * 70)
    print("Effective Supabase S3 config (from settings + .env)")
    print("=" * 70)
    print(f"  endpoint_url   : {endpoint}")
    print(f"  region         : {region}")
    print(f"  access_key_id  : {mask(access_key)}")
    print(f"  secret_key     : {mask(secret_key)}")
    print(f"  public bucket  : {public_bucket!r}")
    print(f"  private bucket : {private_bucket!r}")
    print()

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )

    # ------------------------------------------------------------------
    # 1. list_buckets -- shows every bucket the credentials can see.
    # ------------------------------------------------------------------
    print("=" * 70)
    print("STEP 1: list_buckets() -- buckets actually on this Supabase project")
    print("=" * 70)
    try:
        resp = client.list_buckets()
        buckets = [b["Name"] for b in resp.get("Buckets", [])]
        if not buckets:
            print("  (no buckets found on this project)")
        else:
            for name in buckets:
                print(f"  - {name}")
    except EndpointConnectionError as exc:
        print(f"  CONNECTION ERROR: {exc}")
        print("  -> endpoint URL is wrong or unreachable.")
        return 2
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "?")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        print(f"  CLIENT ERROR ({code}): {msg}")
        if code in ("InvalidAccessKeyId", "SignatureDoesNotMatch"):
            print("  -> credentials are wrong; copy fresh ones from Supabase Dashboard.")
        return 3
    print()

    # ------------------------------------------------------------------
    # 2. head_bucket on each configured bucket -- does Supabase agree?
    # ------------------------------------------------------------------
    print("=" * 70)
    print("STEP 2: head_bucket() on each configured bucket")
    print("=" * 70)
    failed = False
    for label, bucket in [
        ("public ", public_bucket),
        ("private", private_bucket),
    ]:
        try:
            client.head_bucket(Bucket=bucket)
            print(f"  [OK]   {label}  {bucket!r} -- bucket exists and is reachable")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "?")
            print(f"  [FAIL] {label}  {bucket!r} -- {code}")
            failed = True

    print()
    print("=" * 70)
    if failed:
        print("DIAGNOSIS")
        print("=" * 70)
        print(
            "  At least one configured bucket name does NOT match a bucket on\n"
            "  the Supabase project pointed at by SUPABASE_S3_ENDPOINT_URL.\n"
            "\n"
            "  Compare the bucket list in STEP 1 to the .env values:\n"
            f"      SUPABASE_PUBLIC_BUCKET  = {public_bucket!r}\n"
            f"      SUPABASE_PRIVATE_BUCKET = {private_bucket!r}\n"
            "\n"
            "  Either rename the buckets in Supabase Dashboard -> Storage to\n"
            "  match the .env, or update the .env to match the dashboard."
        )
        return 4

    print("All checks passed. Storage is correctly configured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
