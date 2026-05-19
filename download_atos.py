"""Stáhne raw ATOS feed z hurtmeble.eu do lokálního souboru.

Pro použití v GitHub Actions a lokálním běhu — žádné absolutní cesty.

URL: https://hurtmeble.eu/feeds/oferta_hurtowa_PL_PLN.xml
Výchozí výstup: ./out/atos_source_feed.xml

Usage:
    python download_atos.py
    python download_atos.py --out out/atos_source_feed.xml
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import argparse
import hashlib
import time
from pathlib import Path

import requests

URL = "https://hurtmeble.eu/feeds/oferta_hurtowa_PL_PLN.xml"
DEFAULT_OUT = "out/atos_source_feed.xml"


def main():
    parser = argparse.ArgumentParser(description="Stáhne ATOS XML feed")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Výstupní cesta")
    parser.add_argument("--url", default=URL, help="URL ATOS feedu")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] GET {args.url}")
    headers = {
        "User-Agent": "procentov-feed-bot/1.0 (procentov.cz)",
        "Accept": "application/xml,text/xml,*/*",
    }
    t0 = time.time()
    try:
        r = requests.get(args.url, headers=headers, timeout=180, stream=True)
    except requests.RequestException as e:
        print(f"[ERROR] HTTP error: {e}")
        sys.exit(2)

    print(f"      HTTP {r.status_code} | Content-Type: {r.headers.get('Content-Type')}")
    print(f"      Content-Length: {r.headers.get('Content-Length')}")

    if r.status_code != 200:
        print(f"[ERROR] HTTP {r.status_code}")
        print(r.text[:500])
        sys.exit(3)

    print(f"[2/3] Streaming download → {out_path}")
    total = 0
    sha = hashlib.sha256()
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                sha.update(chunk)
    tmp_path.replace(out_path)

    elapsed = time.time() - t0
    mb = total / (1024 * 1024)
    print(f"      Staženo: {total:,} bytes ({mb:.2f} MB) za {elapsed:.1f}s")
    print(f"      SHA256: {sha.hexdigest()}")

    print(f"[3/3] Sanity check (prvních 200 bytes):")
    with open(out_path, "rb") as f:
        head = f.read(200)
    try:
        print(head.decode("utf-8")[:200])
    except UnicodeDecodeError:
        print(head[:200])

    # Minimální kontrola, že je to XML
    if b"<?xml" not in head and b"<offers" not in head and b"<products" not in head:
        print("[WARN] Stažený soubor nezačíná XML deklarací — zkontroluj obsah!")
        sys.exit(4)

    print(f"\n[SUCCESS] ATOS feed stažen: {out_path}")


if __name__ == "__main__":
    main()
