"""M2.3 — Atomic upload na Cloudflare R2 + archive + Healthchecks.io.

Atomic pattern:
  1. Upload do tmp klíče (*.tmp)
  2. Copy tmp → finální klíč
  3. Delete tmp
  4. Archive: copy production → archive/{key}_{YYYYMMDD_HHMMSS}.xml
  5. Cleanup: smazat archivní soubory starší než 30 dnů
  6. Healthchecks.io ping (úspěch nebo fail)
  7. Ověření: HEAD request na veřejnou URL

Konfigurace z Windows Environment Variables:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  HEALTHCHECKS_UUID  (volitelné — pokud chybí, ping se přeskočí)

Změny:
  15.5.2026 — R2_PUBLIC_BASE opraven na pub-*.r2.dev
  15.5.2026 — Přidáno: archive, cleanup po 30 dnech, Healthchecks.io ping

Usage:
    python hosting/upload_r2.py --file out/atos_milo.xml --key atos_milo.xml
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import argparse
import hashlib
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import boto3
from botocore.config import Config
import requests


R2_BUCKET = "procentov-feeds"
R2_PUBLIC_BASE = "https://pub-23c2cbd6ef464916b7ed127c70634076.r2.dev"
ARCHIVE_PREFIX = "archive/"
ARCHIVE_RETENTION_DAYS = 30


def get_r2_client():
    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    missing = [k for k, v in [
        ("R2_ACCOUNT_ID", account_id),
        ("R2_ACCESS_KEY_ID", access_key),
        ("R2_SECRET_ACCESS_KEY", secret_key),
    ] if not v]
    if missing:
        raise EnvironmentError(f"Chybí env variables: {', '.join(missing)}")

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    return client


def upload_atomic(client, data: bytes, final_key: str) -> str:
    """Atomic upload: tmp → copy → delete. Vrací public URL."""
    tmp_key = final_key + ".tmp"

    print(f"  [1/3] Upload tmp: {tmp_key}")
    client.put_object(Bucket=R2_BUCKET, Key=tmp_key, Body=data,
                      ContentType="application/xml; charset=utf-8")

    print(f"  [2/3] Copy → {final_key}")
    client.copy_object(
        Bucket=R2_BUCKET,
        CopySource={"Bucket": R2_BUCKET, "Key": tmp_key},
        Key=final_key,
    )

    print(f"  [3/3] Delete tmp")
    client.delete_object(Bucket=R2_BUCKET, Key=tmp_key)

    return f"{R2_PUBLIC_BASE}/{final_key}"


def archive_feed(client, final_key: str):
    """Zkopíruje production klíč do archive/ se timestampem."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = final_key.replace(".xml", "")
    archive_key = f"{ARCHIVE_PREFIX}{stem}_{ts}.xml"
    print(f"  Archive → {archive_key}")
    client.copy_object(
        Bucket=R2_BUCKET,
        CopySource={"Bucket": R2_BUCKET, "Key": final_key},
        Key=archive_key,
    )
    return archive_key


def cleanup_archive(client, final_key: str):
    """Smaže archivní soubory starší než ARCHIVE_RETENTION_DAYS."""
    stem = final_key.replace(".xml", "")
    prefix = f"{ARCHIVE_PREFIX}{stem}_"
    cutoff = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_RETENTION_DAYS)

    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            last_modified = obj["LastModified"]
            if last_modified < cutoff:
                client.delete_object(Bucket=R2_BUCKET, Key=obj["Key"])
                print(f"  Cleanup smazán: {obj['Key']} ({last_modified.date()})")
                deleted += 1

    if deleted == 0:
        print(f"  Cleanup: žádné soubory starší než {ARCHIVE_RETENTION_DAYS} dní")
    else:
        print(f"  Cleanup: smazáno {deleted} archivních souborů")


def ping_healthchecks(success: bool):
    """Ping Healthchecks.io — UUID z env HEALTHCHECKS_UUID."""
    uuid = os.environ.get("HEALTHCHECKS_UUID", "").strip()
    if not uuid:
        print("  Healthchecks.io: UUID nenastaveno (HEALTHCHECKS_UUID), přeskakuji")
        return

    suffix = "" if success else "/fail"
    url = f"https://hc-ping.com/{uuid}{suffix}"
    try:
        resp = requests.get(url, timeout=10)
        status = "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}"
        print(f"  Healthchecks.io ping: {status} ({url})")
    except requests.RequestException as e:
        print(f"  Healthchecks.io ping selhal: {e}")


def verify_url(url: str) -> bool:
    """HEAD request — ověří dostupnost a neprázdnost."""
    try:
        resp = requests.head(url, timeout=15)
        if resp.status_code == 200:
            size = int(resp.headers.get("Content-Length", 0))
            print(f"  [OK] HTTP 200, Content-Length: {size:,} bytes")
            return True
        print(f"  [ERROR] HTTP {resp.status_code}")
        return False
    except requests.RequestException as e:
        print(f"  [ERROR] {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Atomic upload na Cloudflare R2")
    parser.add_argument("--file", required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()

    local_path = Path(args.file)
    final_key = args.key

    # [1/6] Kontrola souboru
    print(f"[1/6] Kontrola souboru: {local_path}")
    if not local_path.exists() or local_path.stat().st_size == 0:
        print("[ERROR] Soubor neexistuje nebo je prázdný")
        ping_healthchecks(success=False)
        sys.exit(1)
    data = local_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    print(f"[OK] {len(data):,} bytes | SHA256: {sha256}")

    try:
        client = get_r2_client()
    except EnvironmentError as e:
        print(f"[ERROR] {e}")
        ping_healthchecks(success=False)
        sys.exit(1)

    # [2/6] Atomic upload
    print(f"[2/6] Atomic upload...")
    try:
        public_url = upload_atomic(client, data, final_key)
        print(f"[OK] Upload hotov: {public_url}")
    except Exception as e:
        print(f"[ERROR] Upload selhal: {e}")
        ping_healthchecks(success=False)
        sys.exit(1)

    # [3/6] Archive
    print(f"[3/6] Archive...")
    try:
        archive_key = archive_feed(client, final_key)
        print(f"[OK] Archivováno: {archive_key}")
    except Exception as e:
        print(f"[WARN] Archive selhal (nekritické): {e}")

    # [4/6] Cleanup
    print(f"[4/6] Cleanup archivů starších než {ARCHIVE_RETENTION_DAYS} dní...")
    try:
        cleanup_archive(client, final_key)
    except Exception as e:
        print(f"[WARN] Cleanup selhal (nekritické): {e}")

    # [5/6] Ověření URL
    print(f"[5/6] Ověřuji URL: {public_url}")
    ok = verify_url(public_url)
    if not ok:
        print("[WARN] Ověření selhalo (CDN cache?), zkontroluj ručně")

    # [6/6] Healthchecks.io
    print(f"[6/6] Healthchecks.io ping...")
    ping_healthchecks(success=True)

    print(f"\n[SUCCESS] Upload dokončen")
    print(f"  URL:    {public_url}")
    print(f"  Size:   {len(data):,} bytes")
    print(f"  SHA256: {sha256}")


if __name__ == "__main__":
    main()
