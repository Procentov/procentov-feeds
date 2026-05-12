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


# Whitelist atributu - jen tyto sbirame do slovniku jako klice
ATTR_WHITELIST = {
    # Variantni / parametricke z M1.2
    "Kolor",
    "Materiał",
    "Kod_producenta",
    "Producent",
    # Rozmery (rozsireni M1.3 dle empirie ATOS Milo)
    "Wysokość oparcia [cm]",
    "Wysokość do siedziska [cm]",
    "Wysokość do podłokietnika [cm]",
    "Wysokość całkowita [cm]",
    "Głębokość siedziska [cm]",
    "Głębokość całkowita [cm]",
    "Szerokość siedziska [cm]",
    "Szerokość całkowita [cm]",
    "Waga [kg]",
    "Maksymalna waga obciążenia [kg]",
    # Specialni
    "EAN",
    "material_composition",
}

# Whitelist atributu, jejichz HODNOTY sbirame do namespace "hodnoty"
# (pro generic PL->CZ slovnik typu MIKROFAZA -> Mikrovlakno)
VALUE_SOURCE_ATTRS = {
    "Materiał",  # MIKROFAZA, EKO-SKÓRA, VELVET, BRINGHTON 2 atd.
}

# Atribut, jehoz hodnoty jsou barevne kody -> jdou do namespace barvy_kody
COLOR_CODE_ATTR = "Kolor"


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

def is_translatable_pl_string(s: str) -> bool:
    """Vrati True pokud string vypada jako prekladatelny PL string,
    False pokud je to cislo, EAN, symbol kod nebo prazdny string.

    Pravidla:
    - prazdny string -> False
    - obsahuje pouze cislice -> False (12, 250, 5903769305087)
    - matchuje regex symbol kódu (XX-XX-XX-X) -> False
    - obsahuje aspon jedno písmeno -> True
    """
    import re

    if not s or not s.strip():
        return False
    stripped = s.strip()
    # Cista cisla (vc. dlouhych EAN)
    if stripped.replace('-', '').replace('.', '').replace(',', '').isdigit():
        return False
    # Symbol kod typu 3-7-70-9 nebo 10-25-56-12
    if re.fullmatch(r'\d+(-\d+)+', stripped):
        return False
    # Musi obsahovat aspon jedno pismeno
    if not any(c.isalpha() for c in stripped):
        return False
    return True


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
    barvy_kody: Set[str] = set()

    # Procházej všechny produkty a jejich varianty
    for product in products:
        for offer in product.offers:
            # Atributy: názvy atributů - POUZE z whitelistu
            for attr in offer.attributes:
                if attr.name_pl and attr.name_pl in ATTR_WHITELIST:
                    atributy.add(attr.name_pl)

                # Hodnoty: hodnoty atributů z VALUE_SOURCE_ATTRS (s filtrem)
                if attr.name_pl in VALUE_SOURCE_ATTRS:
                    for value in attr.values_pl:
                        if value and is_translatable_pl_string(value):
                            hodnoty.add(value)

                # Barevné kódy: hodnoty z COLOR_CODE_ATTR (BEZ filtru)
                if attr.name_pl == COLOR_CODE_ATTR:
                    for value in attr.values_pl:
                        if value:
                            barvy_kody.add(value)

            # Kategorie: JEDNOTLIVÉ SEGMENTY z cat_path_pl
            for segment in offer.cat_path_pl:
                if segment:
                    kategorie.add(segment)

    print(f"Unikátní stringy:")
    print(f"  - atributy: {len(atributy)}")
    print(f"  - hodnoty: {len(hodnoty)}")
    print(f"  - kategorie: {len(kategorie)}")
    print(f"  - barvy_kody: {len(barvy_kody)}")

    # Vytvoř výstupní strukturu s null hodnotami
    output = {
        "schema_version": "1.0",
        "updated_at": get_iso_timestamp(),
        "namespaces": {
            "atributy": {key: None for key in sorted(atributy)},
            "hodnoty": {key: None for key in sorted(hodnoty)},
            "kategorie": {key: None for key in sorted(kategorie)},
            "barvy_kody": {
                key: {"pl": None, "cz": None, "material": None}
                for key in sorted(barvy_kody)
            }
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
    # POZOR: barvy_kody se NEpřekládají - hodnoty pocházejí ze seedu nebo Mirkovy revize
    timestamp = get_iso_timestamp()
    total_translated = 0

    for namespace_name in ['atributy', 'hodnoty', 'kategorie']:
        namespace_dict = data['namespaces'].get(namespace_name, {})
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
    3. Zapíše target NA DISK (před validací - aby silent fail printu nezničil zápis)
    4. Validuje proti schema (poté může sys.exit(1) v případě chyby)
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
    for namespace_name in ['atributy', 'hodnoty', 'kategorie', 'barvy_kody']:
        review_ns = review['namespaces'].get(namespace_name, {})
        target_ns = target['namespaces'].get(namespace_name, {})

        for pl_key, value in review_ns.items():
            # Pro barvy_kody: skip pokud vsechny 3 fieldy (pl, cz, material) jsou null
            if namespace_name == 'barvy_kody':
                if not isinstance(value, dict) or all(v is None for v in value.values()):
                    continue
            else:
                # Pro string namespaces: skip null
                if value is None:
                    continue

            # Není v target -> přidej
            if pl_key not in target_ns:
                target_ns[pl_key] = value
                target['audit'][pl_key] = {
                    "_source": "review",
                    "_reviewed_by": "mirek",
                    "_updated_at": timestamp
                }
                added += 1

            # Je v target a liší se -> update
            elif target_ns[pl_key] != value:
                old_value = target_ns[pl_key]
                target_ns[pl_key] = value

                # Update audit
                target['audit'][pl_key] = {
                    "_source": "review",
                    "_reviewed_by": "mirek",
                    "_updated_at": timestamp
                }

                print(f"UPDATE: {pl_key} | {old_value} -> {value}")
                updated += 1

            # Je stejný -> skip
            else:
                skipped += 1

    # Aktualizuj timestamp v targetu
    target['updated_at'] = timestamp

    print(f"\nSouhrn:")
    print(f"  Pridano: {added}")
    print(f"  Aktualizovano: {updated}")
    print(f"  Preskoceno (shodne): {skipped}")

    # POZOR: ulozit PRED validaci, aby silent fail printu nezablokoval zapis.
    # Validace muze stale udelat sys.exit(1), ale soubor uz bude na disku
    # a uzivatel vidi v stdoutu, ze se neco ulozilo.
    save_json(target, args.target)
    print(f"Ulozeno do: {args.target}")

    # Validuj proti schema (az ted, kdyz je soubor na disku)
    schema_path = Path(__file__).parent / 'slovnik_schema.json'
    print(f"\nValiduji proti: {schema_path}")
    validate_schema(target, str(schema_path))
    print("[OK] Validace uspesna")


# ============================================================================
# SEED: Merge seedu (dekódovací tabulky) do slovníku
# ============================================================================

def cmd_seed(args) -> None:
    """Mergne seed (dekódovací tabulku) do cílového slovníku.

    Logika:
    1. Načte source (seed JSON) a target (slovník)
    2. Pro každý záznam v source["barvy_kody"]:
       - Pokud v target neexistuje -> přidá + audit "_source": "seed_utuli"
       - Pokud existuje a liší se -> log WARN + ZACHOVÁ stávající target
       - Pokud shodné -> skip
    3. Zapíše target NA DISK (před validací - aby silent fail printu nezničil zápis)
    4. Validuje proti schema
    """
    print(f"Aplikuji seed:")
    print(f"  Source: {args.source}")
    print(f"  Target: {args.target}")

    # Načti soubory
    source = load_json(args.source)
    target = load_json(args.target)

    # Počítadla změn
    added = 0
    skipped = 0
    conflicts = 0
    timestamp = get_iso_timestamp()

    # Procházej barvy_kody ze seedu
    source_barvy = source.get('barvy_kody', {})
    target_barvy = target['namespaces'].get('barvy_kody', {})

    for kod, seed_value in source_barvy.items():
        # Není v target -> přidej
        if kod not in target_barvy:
            target_barvy[kod] = seed_value
            target['audit'][kod] = {
                "_source": "seed_utuli",
                "_updated_at": timestamp
            }
            added += 1

        # Je v target a liší se -> WARN, ZACHOVEJ target (seed nepřepisuje revizi)
        elif target_barvy[kod] != seed_value:
            print(f"WARN: SEED-CONFLICT: {kod} (zachovana target hodnota)")
            conflicts += 1

        # Je stejný -> skip
        else:
            skipped += 1

    # Aktualizuj timestamp v targetu
    target['updated_at'] = timestamp

    print(f"\nSouhrn:")
    print(f"  Pridano ze seedu: {added}")
    print(f"  Preskoceno (shodne): {skipped}")
    print(f"  Konfliktu (seed != target): {conflicts}")

    # Ulozit PRED validaci (viz cmd_merge dokumentace)
    save_json(target, args.target)
    print(f"Ulozeno do: {args.target}")

    # Validuj proti schema
    schema_path = Path(__file__).parent / 'slovnik_schema.json'
    print(f"\nValiduji proti: {schema_path}")
    validate_schema(target, str(schema_path))
    print("[OK] Validace uspesna")


# ============================================================================
# MAIN: Argparse CLI
# ============================================================================

def main():
    """Hlavní entry point s argparse subparsers."""
    # Pokud bezime na Windows v cp1250 prostredi, prepnout stdout/stderr
    # na UTF-8. Bez tohoto print s non-ASCII znaky (cestina, sipky) pada.
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

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

    # SEED subcommand
    parser_seed = subparsers.add_parser(
        'seed',
        help='Mergne seed (dekódovací tabulku) do slovníku'
    )
    parser_seed.add_argument(
        '--source',
        required=True,
        help='Seed JSON soubor (barvy_kody)'
    )
    parser_seed.add_argument(
        '--target',
        required=True,
        help='Cílový slovník JSON (slovnik.json)'
    )
    parser_seed.set_defaults(func=cmd_seed)

    # Parse args a zavolej příslušnou funkci
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
