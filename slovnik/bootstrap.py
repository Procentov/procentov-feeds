"""Slovník PL->CZ bootstrap toolkit.

Příkazy:
  extract   - Extrahuje unikátní PL stringy z XML feedu
  translate - Přeloží stringy pomocí Google Translate API
  merge     - Mergne zrevidovaný draft do cílového slovníku
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

# Import parseru z polotovaru
sys.path.insert(0, str(Path(__file__).parent.parent))
from polotovar.parser_atos import parse as parse_atos


def load_json(path: str) -> dict:
    """Načte JSON soubor."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: dict, path: str) -> None:
    """Uloží JSON soubor s pěkným formátováním."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')  # Trailing newline


def get_iso_timestamp() -> str:
    """Vrátí aktuální timestamp ve formátu ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def validate_schema(data: dict, schema_path: str) -> None:
    """Validuje data proti JSON Schema.

    Raises:
        SystemExit: Pokud validace selže
    """
    try:
        import jsonschema
    except ImportError:
        print("Chyba: Balíček 'jsonschema' není nainstalován.", file=sys.stderr)
        print("Spusť: pip install jsonschema", file=sys.stderr)
        sys.exit(1)

    schema = load_json(schema_path)

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        print(f"Chyba validace: {e.message}", file=sys.stderr)
        print(f"Cesta: {' -> '.join(str(p) for p in e.path)}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.SchemaError as e:
        print(f"Chyba ve schématu: {e.message}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# EXTRACT: Extrakce unikátních PL stringů z XML feedu
# ============================================================================

def cmd_extract(args) -> None:
    """Extrahuje unikátní PL stringy z XML feedu do JSON souboru.

    Logika:
    1. Parsuje XML pomocí polotovar.parser_atos.parse()
    2. Sbírá unikátní stringy ze tří namespaces:
       - atributy: názvy atributů (attr.name_pl)
       - hodnoty: hodnoty atributů (attr.values_pl)
       - kategorie: jednotlivé segmenty z cat_path_pl
    3. Vytvoří JSON s null hodnotami pro všechny stringy
    """
    print(f"Extrahuji stringy z: {args.xml}")
    print(f"Filtr kategorie: {args.category or '(žádný)'}")

    # Parsuj XML pomocí existujícího parseru
    try:
        products = parse_atos(args.xml, category_filter=args.category)
    except Exception as e:
        print(f"Chyba při parsování XML: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Naparsováno {len(products)} produktů (master groups)")

    # Inicializuj sety pro unikátní stringy
    atributy: Set[str] = set()
    hodnoty: Set[str] = set()
    kategorie: Set[str] = set()

    # Procházej všechny produkty a jejich varianty
    for product in products:
        for offer in product.offers:
            # Atributy: názvy atributů
            for attr in offer.attributes:
                if attr.name_pl:
                    atributy.add(attr.name_pl)

                # Hodnoty: hodnoty atributů (attr.values_pl je list)
                for value in attr.values_pl:
                    if value:
                        hodnoty.add(value)

            # Kategorie: JEDNOTLIVÉ SEGMENTY z cat_path_pl
            for segment in offer.cat_path_pl:
                if segment:
                    kategorie.add(segment)

    print(f"Unikátní stringy:")
    print(f"  - atributy: {len(atributy)}")
    print(f"  - hodnoty: {len(hodnoty)}")
    print(f"  - kategorie: {len(kategorie)}")

    # Vytvoř výstupní strukturu s null hodnotami
    output = {
        "schema_version": "1.0",
        "updated_at": get_iso_timestamp(),
        "namespaces": {
            "atributy": {key: None for key in sorted(atributy)},
            "hodnoty": {key: None for key in sorted(hodnoty)},
            "kategorie": {key: None for key in sorted(kategorie)}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Ulož výstup
    save_json(output, args.out)
    print(f"Uloženo do: {args.out}")


# ============================================================================
# TRANSLATE: Překlad pomocí Google Translate API
# ============================================================================

def cmd_translate(args) -> None:
    """Přeloží null hodnoty v slovníku pomocí Google Translate API.

    Logika:
    1. Načte GOOGLE_TRANSLATE_API_KEY z env
    2. Pro každou null hodnotu v namespaces zavolá PL->CS překlad
    3. Batch po max 100 stringů (Google Translate limit)
    4. Vypíná překlad + audit entry
    5. Idempotentní: pokud hodnota není null, zachová a přeskočí
    """
    print(f"Překládám: {args.input}")

    # Zkontroluj API klíč
    api_key = os.environ.get('GOOGLE_TRANSLATE_API_KEY', '').strip()
    if not api_key:
        print("Chyba: GOOGLE_TRANSLATE_API_KEY env var chybí.", file=sys.stderr)
        print("Pokud byl klíč nedávno přidán, restartuj Vrátný+Tunel", file=sys.stderr)
        print("(4 ikony na ploše: STOP/START obojího).", file=sys.stderr)
        sys.exit(1)

    # Načti vstupní slovník
    data = load_json(args.input)

    # Import Google Translate
    try:
        from google.cloud import translate_v2 as translate
    except ImportError:
        print("Chyba: google-cloud-translate není nainstalován.", file=sys.stderr)
        print("Spusť: pip install google-cloud-translate", file=sys.stderr)
        sys.exit(1)

    # Inicializuj klienta
    try:
        # Pro REST API klíč použijeme client bez credentials
        # (google-cloud-translate používá env var GOOGLE_APPLICATION_CREDENTIALS,
        # ale my máme GOOGLE_TRANSLATE_API_KEY pro REST API)
        # Použijeme radši přímé REST volání
        import requests
    except ImportError:
        print("Chyba: requests není nainstalován.", file=sys.stderr)
        print("Spusť: pip install requests", file=sys.stderr)
        sys.exit(1)

    def translate_batch(strings: list[str]) -> dict[str, str]:
        """Přeloží batch stringů pomocí Google Translate REST API."""
        url = "https://translation.googleapis.com/language/translate/v2"

        # Google Translate API podporuje max 128 stringů v jednom requestu,
        # ale používáme limit 100 pro bezpečnost
        if len(strings) > 100:
            raise ValueError(f"Batch příliš velký: {len(strings)} > 100")

        params = {
            'key': api_key,
            'source': 'pl',
            'target': 'cs',
            'format': 'text',
            'q': strings  # Pole stringů k překladu
        }

        try:
            response = requests.post(url, params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Chyba při volání Google Translate API: {e}", file=sys.stderr)
            sys.exit(1)

        result_data = response.json()

        if 'data' not in result_data or 'translations' not in result_data['data']:
            print(f"Neočekávaná odpověď z API: {result_data}", file=sys.stderr)
            sys.exit(1)

        # Vrátí slovník PL -> CS
        translations = {}
        for i, translation in enumerate(result_data['data']['translations']):
            translations[strings[i]] = translation['translatedText']

        return translations

    # Procházej všechny namespaces a překládej null hodnoty
    timestamp = get_iso_timestamp()
    total_translated = 0

    for namespace_name, namespace_dict in data['namespaces'].items():
        # Najdi všechny klíče s null hodnotou
        to_translate = [key for key, value in namespace_dict.items() if value is None]

        if not to_translate:
            print(f"Namespace '{namespace_name}': žádné null hodnoty")
            continue

        print(f"Namespace '{namespace_name}': překládám {len(to_translate)} stringů...")

        # Překládej po batchích max 100 stringů
        batch_size = 100
        for i in range(0, len(to_translate), batch_size):
            batch = to_translate[i:i+batch_size]
            print(f"  Batch {i//batch_size + 1}/{(len(to_translate)-1)//batch_size + 1} ({len(batch)} stringů)...")

            # Zavolej Google Translate
            translations = translate_batch(batch)

            # Aplikuj překlady
            for pl_string, cs_string in translations.items():
                namespace_dict[pl_string] = cs_string

                # Přidej audit entry
                data['audit'][pl_string] = {
                    "_source": "google",
                    "_updated_at": timestamp
                }

                total_translated += 1

    # Aktualizuj timestamp
    data['updated_at'] = timestamp

    # Ulož výstup
    save_json(data, args.out)
    print(f"Přeloženo {total_translated} stringů")
    print(f"Uloženo do: {args.out}")


# ============================================================================
# MERGE: Merge zrevidovaného draftu do cílového slovníku
# ============================================================================

def cmd_merge(args) -> None:
    """Mergne zrevidovaný draft do cílového slovníku.

    Logika:
    1. Načte target (existující slovník) a review (zrevidovaný draft)
    2. Pro každý string v review namespaces:
       - Pokud není v target -> přidá + audit
       - Pokud je a liší se -> přepíše + print UPDATE
       - Pokud je stejný -> skip
    3. Validuje proti schema
    4. Zapíše target na disk
    """
    print(f"Merguji:")
    print(f"  Review: {args.review}")
    print(f"  Target: {args.target}")

    # Načti soubory
    review = load_json(args.review)
    target = load_json(args.target)

    # Počítadla změn
    added = 0
    updated = 0
    skipped = 0
    timestamp = get_iso_timestamp()

    # Procházej všechny namespaces v review
    for namespace_name in ['atributy', 'hodnoty', 'kategorie']:
        review_ns = review['namespaces'].get(namespace_name, {})
        target_ns = target['namespaces'].get(namespace_name, {})

        for pl_key, cs_value in review_ns.items():
            # Skip null hodnoty v review (ještě nepřeložené)
            if cs_value is None:
                continue

            # Není v target -> přidej
            if pl_key not in target_ns:
                target_ns[pl_key] = cs_value
                target['audit'][pl_key] = {
                    "_source": "review",
                    "_reviewed_by": "mirek",
                    "_updated_at": timestamp
                }
                added += 1

            # Je v target a liší se -> update
            elif target_ns[pl_key] != cs_value:
                old_value = target_ns[pl_key]
                target_ns[pl_key] = cs_value

                # Update audit
                target['audit'][pl_key] = {
                    "_source": "review",
                    "_reviewed_by": "mirek",
                    "_updated_at": timestamp
                }

                print(f"UPDATE: {pl_key} | {old_value} -> {cs_value}")
                updated += 1

            # Je stejný -> skip
            else:
                skipped += 1

    # Aktualizuj timestamp v targetu
    target['updated_at'] = timestamp

    print(f"\nSouhrn:")
    print(f"  Přidáno: {added}")
    print(f"  Aktualizováno: {updated}")
    print(f"  Přeskočeno (shodné): {skipped}")

    # Validuj proti schema
    schema_path = Path(__file__).parent / 'slovnik_schema.json'
    print(f"\nValiduji proti: {schema_path}")
    validate_schema(target, str(schema_path))
    print("✓ Validace úspěšná")

    # Ulož target
    save_json(target, args.target)
    print(f"Uloženo do: {args.target}")


# ============================================================================
# MAIN: Argparse CLI
# ============================================================================

def main():
    """Hlavní entry point s argparse subparsers."""
    parser = argparse.ArgumentParser(
        description='Slovník PL->CZ bootstrap toolkit',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', required=True, help='Příkazy')

    # EXTRACT subcommand
    parser_extract = subparsers.add_parser(
        'extract',
        help='Extrahuje unikátní PL stringy z XML feedu'
    )
    parser_extract.add_argument(
        '--xml',
        required=True,
        help='Cesta k ATOS XML feedu'
    )
    parser_extract.add_argument(
        '--category',
        help='Filtr kategorie (case-insensitive substring match)'
    )
    parser_extract.add_argument(
        '--out',
        required=True,
        help='Výstupní JSON soubor'
    )
    parser_extract.set_defaults(func=cmd_extract)

    # TRANSLATE subcommand
    parser_translate = subparsers.add_parser(
        'translate',
        help='Přeloží stringy pomocí Google Translate API'
    )
    parser_translate.add_argument(
        '--in',
        dest='input',
        required=True,
        help='Vstupní JSON soubor (output z extract)'
    )
    parser_translate.add_argument(
        '--out',
        required=True,
        help='Výstupní JSON soubor (draft k review)'
    )
    parser_translate.set_defaults(func=cmd_translate)

    # MERGE subcommand
    parser_merge = subparsers.add_parser(
        'merge',
        help='Mergne zrevidovaný draft do cílového slovníku'
    )
    parser_merge.add_argument(
        '--review',
        required=True,
        help='Zrevidovaný draft JSON'
    )
    parser_merge.add_argument(
        '--target',
        required=True,
        help='Cílový slovník JSON (slovnik.json)'
    )
    parser_merge.set_defaults(func=cmd_merge)

    # Parse args a zavolej příslušnou funkci
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
