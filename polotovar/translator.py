"""Prekladac PL → CZ pres slovnik/slovnik.json.

Podporuje 3 namespaces:
- atributy (nazvy atributu: Kolor → Barva)
- hodnoty (hodnoty atributu: Velvet → Samet)
- kategorie (nazvy kategorii: FOTELE → Kresla)

Plus specialni namespace barvy_kody pro dekodovani kodu typu "MG02", "1D" atd.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import json
from pathlib import Path
from typing import Optional


def load_slovnik(slovnik_path: str | Path) -> dict:
    """Nacte slovnik/slovnik.json.

    Args:
        slovnik_path: Cesta ke slovniku

    Returns:
        dict se strukturou {namespaces: {atributy: {}, hodnoty: {}, kategorie: {}, barvy_kody: {}}, ...}

    Raises:
        ValueError: Pokud slovnik neni platny JSON nebo chybi povinne namespaces
    """
    slovnik_path = Path(slovnik_path)
    if not slovnik_path.exists():
        raise ValueError(f"Slovnik neexistuje: {slovnik_path}")

    with open(slovnik_path, 'r', encoding='utf-8') as f:
        slovnik = json.load(f)

    # Validace struktury
    if 'namespaces' not in slovnik:
        raise ValueError("Slovnik nema 'namespaces' klic")

    required_ns = {'atributy', 'hodnoty', 'kategorie'}
    if not required_ns.issubset(slovnik['namespaces'].keys()):
        raise ValueError(f"Slovnik chybi povinne namespaces: {required_ns}")

    return slovnik


def translate_attribute_name(pl_name: str, slovnik: dict, kategorie_context: Optional[str] = None) -> str:
    """Prelozi nazev atributu z PL na CZ.

    Args:
        pl_name: Polsky nazev atributu (napr. "Kolor")
        slovnik: Nacteny slovnik
        kategorie_context: Volitelny kontext kategorie pro per-kategorii override

    Returns:
        CZ preklad nebo PL fallback pokud neni v slovniku (+ warning log)
    """
    # Check per-kategorii override
    if kategorie_context:
        per_kat = slovnik.get('per_kategorii_override', {}).get(kategorie_context, {})
        if pl_name in per_kat:
            return per_kat[pl_name]

    # Check globalni namespace
    atributy_ns = slovnik['namespaces']['atributy']
    if pl_name in atributy_ns:
        return atributy_ns[pl_name]

    # Fallback: vrat PL (validator pak chytne BLOCK-9 polske diakritiky)
    print(f"[WARNING] Attribute name '{pl_name}' neni v slovniku, pouzit PL fallback")
    return pl_name


def translate_attribute_value(pl_value: str, slovnik: dict) -> str:
    """Prelozi hodnotu atributu z PL na CZ.

    Args:
        pl_value: Polska hodnota (napr. "VELVET")
        slovnik: Nacteny slovnik

    Returns:
        CZ preklad nebo PL fallback pokud neni v slovniku
    """
    hodnoty_ns = slovnik['namespaces']['hodnoty']
    if pl_value in hodnoty_ns:
        return hodnoty_ns[pl_value]

    # Fallback
    print(f"[WARNING] Attribute value '{pl_value}' neni v slovniku, pouzit PL fallback")
    return pl_value


def translate_category_segment(pl_segment: str, slovnik: dict) -> str:
    """Prelozi jeden segment kategorie z PL na CZ.

    Args:
        pl_segment: Jeden segment kategorialni cesty (napr. "FOTELE")
        slovnik: Nacteny slovnik

    Returns:
        CZ preklad nebo PL fallback
    """
    kategorie_ns = slovnik['namespaces']['kategorie']
    if pl_segment in kategorie_ns:
        return kategorie_ns[pl_segment]

    # Fallback
    print(f"[WARNING] Category segment '{pl_segment}' neni v slovniku, pouzit PL fallback")
    return pl_segment


def decode_color_code(kod: str, slovnik: dict) -> tuple[str, Optional[str]]:
    """Dekoduje barevny kod typu "MG02", "1D", "BL75" na (cz_barva, material).

    Args:
        kod: Barevny kod (napr. "MG02")
        slovnik: Nacteny slovnik

    Returns:
        (cz_barva, material) tuple. Pokud kod neni v slovniku, vraci (kod, None) + warning.

    Priklad:
        decode_color_code("MG02", slovnik) -> ("svestkova", "Velvet")
        decode_color_code("1D", slovnik) -> ("cerna", "Eko-kuze")
    """
    if 'barvy_kody' not in slovnik['namespaces']:
        print(f"[WARNING] Slovnik nema namespace 'barvy_kody', kod '{kod}' nelze dekodovat")
        return (kod, None)

    barvy_kody_ns = slovnik['namespaces']['barvy_kody']
    if kod in barvy_kody_ns:
        entry = barvy_kody_ns[kod]
        cz_barva = entry.get('cz', kod)  # fallback na kod pokud 'cz' chybi
        material = entry.get('material')
        return (cz_barva, material)

    # Fallback
    print(f"[WARNING] Color code '{kod}' neni v slovniku barvy_kody, pouzit kod jako barvu")
    return (kod, None)
