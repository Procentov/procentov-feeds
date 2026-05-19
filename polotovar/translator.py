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


# Schválené překlady popisů produktů (Mirek, 15.5.2026)
# Zdroj: validace přes orchestrátor (4/5 vendorů), tón pro prémiový CZ e-shop
DESCRIPTIONS_CZ = {
    "FOTEL MILO": (
        "Po náročném dni si konečně sednout a nemuset se za půl hodiny zvedat, "
        "protože vás bolí záda. Křeslo Milo vás obklopí měkkým čalouněním a opěradlo "
        "podpírá bedra přesně tam, kde to potřebujete — aniž byste o tom přemýšleli. "
        "Ráno u kávy, večer s knihou nebo jen tak v tichu. Je to místo v obýváku, "
        "které si brzy zamilujete. Vyberte si ze sametu, mikrovlákna nebo ekokůže — "
        "každý materiál má jiný charakter, ale jedno mají společné: nebudete chtít vstávat."
    ),
    "SOFA MILO": (
        "Někdy chcete odpočívat sami, jindy s partnerem nebo s dětmi. Pohovka Milo "
        "má místa dost na obojí. Opěradlo drží záda i při delším filmu a čalounění "
        "si zachová svůj vzhled i po letech každodenního používání. Dáte-li ji dohromady "
        "s křeslem Milo, obývák působí uspořádaně a útulně — jako by tam vždycky patřila. "
        "Ve výsledku je to pohovka, u které prostě zůstanete sedět."
    ),
}

# Výchozí popis pro produkty bez schváleného překladu
DEFAULT_DESCRIPTION = "Popis bude doplněn"


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
    """Prelozi nazev atributu z PL na CZ."""
    if kategorie_context:
        per_kat = slovnik.get('per_kategorii_override', {}).get(kategorie_context, {})
        if pl_name in per_kat:
            return per_kat[pl_name]

    atributy_ns = slovnik['namespaces']['atributy']
    if pl_name in atributy_ns:
        return atributy_ns[pl_name]

    print(f"[WARNING] Attribute name '{pl_name}' neni v slovniku, pouzit PL fallback")
    return pl_name


def translate_attribute_value(pl_value: str, slovnik: dict) -> str:
    """Prelozi hodnotu atributu z PL na CZ."""
    hodnoty_ns = slovnik['namespaces']['hodnoty']
    if pl_value in hodnoty_ns:
        return hodnoty_ns[pl_value]

    if 'barvy_kody' in slovnik['namespaces']:
        barvy_kody_ns = slovnik['namespaces']['barvy_kody']
        if pl_value in barvy_kody_ns:
            entry = barvy_kody_ns[pl_value]
            return entry.get('cz', pl_value)

    print(f"[WARNING] Attribute value '{pl_value}' neni v slovniku, pouzit PL fallback")
    return pl_value


def translate_category_segment(pl_segment: str, slovnik: dict) -> str:
    """Prelozi jeden segment kategorie z PL na CZ."""
    kategorie_ns = slovnik['namespaces']['kategorie']
    if pl_segment in kategorie_ns:
        return kategorie_ns[pl_segment]

    print(f"[WARNING] Category segment '{pl_segment}' neni v slovniku, pouzit PL fallback")
    return pl_segment


def decode_color_code(kod: str, slovnik: dict) -> tuple[str, Optional[str]]:
    """Dekoduje barevny kod typu "MG02", "1D", "BL75" na (cz_barva, material)."""
    if 'barvy_kody' not in slovnik['namespaces']:
        print(f"[WARNING] Slovnik nema namespace 'barvy_kody', kod '{kod}' nelze dekodovat")
        return (kod, None)

    barvy_kody_ns = slovnik['namespaces']['barvy_kody']
    if kod in barvy_kody_ns:
        entry = barvy_kody_ns[kod]
        cz_barva = entry.get('cz', kod)
        material = entry.get('material')
        return (cz_barva, material)

    print(f"[WARNING] Color code '{kod}' neni v slovniku barvy_kody, pouzit kod jako barvu")
    return (kod, None)


def translate_description(desc_pl: str, product_name: str = "") -> str:
    """Vrátí schválený CZ popis produktu.

    Překlady jsou ručně schváleny Mirkem (15.5.2026) a uloženy v DESCRIPTIONS_CZ.
    Pokud produkt není v tabulce, vrátí DEFAULT_DESCRIPTION.

    NIKDY nevracet polský text — validator chytí BLOCK-9 (polské diakritiky).

    Args:
        desc_pl: Původní polský popis (ignorován — používáme schválené překlady)
        product_name: ID produktu (napr. "FOTEL MILO") pro výběr správného překladu

    Returns:
        Schválený CZ text nebo DEFAULT_DESCRIPTION
    """
    if product_name and product_name in DESCRIPTIONS_CZ:
        return DESCRIPTIONS_CZ[product_name]

    # Fallback pro neznámé produkty
    print(f"[WARNING] Popis pro '{product_name}' neni v DESCRIPTIONS_CZ, pouzit default")
    return DEFAULT_DESCRIPTION
