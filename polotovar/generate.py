"""CLI generátor polotovaru v2.0.

Pipeline:
1. Parser ATOS XML → List[ParsedProduct]
2. Load overrides, slovnik
3. Merge variants → List[Product] (pydantic)
4. Build Polotovar objekt
5. Validator (blocking gate)
6. PASS: save polotovar JSON + validation_errors.json
   BLOCKED: save validation_errors.json, exit 1

Usage:
    python polotovar/generate.py --supplier atos --category milo
    python polotovar/generate.py --supplier atos --category milo --xml C:/work/mergado-api/atos_source_feed.xml
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import argparse
import json
from pathlib import Path
from datetime import datetime

from polotovar.parser_atos import parse as parse_atos
from polotovar.pricing import load_overrides
from polotovar.variants import merge_variants
from polotovar.schema import Polotovar
from polotovar.validator import validate


def main():
    parser = argparse.ArgumentParser(description="Generuje polotovar v2.0")
    parser.add_argument("--supplier", required=True, choices=["atos", "art_decoration"], help="Dodavatel")
    parser.add_argument("--category", required=True, help="Kategorie (napr. milo)")
    parser.add_argument("--xml", default="C:/work/mergado-api/atos_source_feed.xml", help="Cesta k ATOS XML")
    parser.add_argument("--overrides", default="cenove_overridy.csv", help="Cesta k cenove_overridy.csv")
    parser.add_argument("--slovnik", default="slovnik/slovnik.json", help="Cesta ke slovniku")
    parser.add_argument("--out", default="out", help="Vystupni adresar")

    args = parser.parse_args()

    print(f"[1/6] Parsovani {args.supplier} XML...")
    try:
        if args.supplier == "atos":
            parsed_products = parse_atos(args.xml, args.category)
            print(f"[OK] Naparsovano {len(parsed_products)} master produktu")
        else:
            print(f"[ERROR] Supplier '{args.supplier}' zatim nepodporovany")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Parsing selhal: {e}")
        sys.exit(1)

    print(f"[2/6] Nacitani cenove_overridy.csv...")
    try:
        overrides = load_overrides(args.overrides)
        print(f"[OK] Nacteno {len(overrides)} overridu")
    except Exception as e:
        print(f"[ERROR] Load overrides selhal: {e}")
        sys.exit(1)

    print(f"[3/6] Merge variant...")
    try:
        products = merge_variants(parsed_products, args.slovnik, overrides)
        total_variants = sum(len(p.variants) for p in products)
        print(f"[OK] Sloučeno na {len(products)} master produktu, {total_variants} variant celkem")
    except Exception as e:
        print(f"[ERROR] Merge variants selhal: {e}")
        sys.exit(1)

    print(f"[4/6] Build Polotovar objekt...")
    try:
        polotovar = Polotovar(
            supplier=args.supplier,
            category=args.category,
            generated_at=datetime.utcnow().isoformat() + "Z",
            schema_version="2.0",
            products=products
        )
        print(f"[OK] Polotovar vytvoren")
    except Exception as e:
        print(f"[ERROR] Build polotovar selhal: {e}")
        sys.exit(1)

    print(f"[5/6] Validace...")
    validation_result = validate(polotovar, args.category)

    if validation_result.verdict == "BLOCKED":
        print(f"[ERROR] Validace BLOCKED: {len(validation_result.blocking_errors)} blocking errors")

        # Save validation_errors.json
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        validation_path = out_dir / "validation_errors.json"

        with open(validation_path, 'w', encoding='utf-8') as f:
            json.dump(validation_result.model_dump(), f, indent=2, ensure_ascii=False)

        print(f"[SAVED] {validation_path}")

        # Vypis prvnich par chyb pro debug
        print(f"\nBlocking errors (prvnich 5):")
        for err in validation_result.blocking_errors[:5]:
            print(f"  - {err.rule}: {err.detail} (product_id={err.product_id})")

        sys.exit(1)
    else:
        print(f"[OK] Validace PASS: {len(validation_result.warnings)} warnings")

    print(f"[6/6] Ukladani vystupu...")
    try:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save polotovar JSON
        polotovar_path = out_dir / f"polotovar_{args.supplier}_{args.category}.json"
        with open(polotovar_path, 'w', encoding='utf-8') as f:
            f.write(polotovar.model_dump_json(indent=2))
        print(f"[SAVED] {polotovar_path}")

        # Save validation_errors.json (i pri PASS, audit trail)
        validation_path = out_dir / "validation_errors.json"
        with open(validation_path, 'w', encoding='utf-8') as f:
            json.dump(validation_result.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"[SAVED] {validation_path}")

        print(f"\n[SUCCESS] Polotovar vygenerovany: verdict={validation_result.verdict}")
        print(f"  - Produktu: {len(polotovar.products)}")
        total_variants = sum(len(p.variants) for p in polotovar.products)
        print(f"  - Variant celkem: {total_variants}")
        print(f"  - Warnings: {len(validation_result.warnings)}")

    except Exception as e:
        print(f"[ERROR] Ukladani selhalo: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
