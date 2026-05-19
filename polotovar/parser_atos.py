"""Parser ATOS XML (Ceneo.pl formát) → strukturované Python objekty.

Bere surový ATOS XML, vrací ParsedProduct objekty (polské texty zachovány).
Translation, pricing, sloučení variant na pydantic = M1.3, MIMO SCOPE.

Struktura obrázků v ATOS XML:
  <imgs>
    <main url="https://hurtmeble.eu/.../export.jpg"/>   ← hlavní, URL jako atribut
    <i url="https://hurtmeble.eu/.../export.jpg"/>       ← ostatní, URL jako atribut
  </imgs>

Změny:
  15.5.2026 — Fix: parser hledal <img> s textem, ATOS má <main>/<i> s url atributem.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import re
from typing import Optional
from lxml import etree
import yaml


@dataclass
class ImageRaw:
    url: str
    is_main: bool


@dataclass
class ParsedAttribute:
    name_pl: str
    values_pl: list[str]
    is_variant: bool  # klasifikace podle whitelist z atos.yaml


@dataclass
class ParsedOffer:
    """Jeden <o> = jedna varianta v ATOS terminologii."""
    id: str
    name_pl: str
    cat_pl: str            # normalizovana, strip whitespace, single-line
    cat_path_pl: list[str] # split po '/'
    desc_pl: str
    price_pln: Decimal
    stock: int
    avail: str             # "in_stock" / "out_of_stock" / "preorder" podle ATOS avail atributu
    url: str
    symbol: str | None     # muze byt None (caste u Milo)
    ean: str | None        # extrahovano z URL regexem, fallback None
    images: list[ImageRaw]
    attributes: list[ParsedAttribute]
    item_group_key: str    # = cat_path[1], nazev produktu (FOTEL MILO, SOFA MILO)
    subcategory_pl: str | None  # cat_path[2] pokud existuje, jinak None (materialova podkategorie)


@dataclass
class ParsedProduct:
    """Master produkt = N variant se stejnym item_group_key."""
    item_group_key: str
    cat_path_pl: list[str]    # spolecna cast (cat bez posledniho segmentu)
    offers: list[ParsedOffer] # varianty


def _load_config() -> dict:
    """Načte config/atos.yaml."""
    config_path = Path(__file__).parent.parent / "config" / "atos.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _normalize_category(cat: str) -> str:
    """Normalizuje kategorii: strip whitespace, single-line."""
    return re.sub(r'\s+', ' ', cat).strip()


def _extract_ean(url: str, regex_pattern: str) -> str | None:
    """Extrahuje EAN z URL pomocí regexu, vrací None pokud selže."""
    try:
        match = re.search(regex_pattern, url)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _map_avail(avail_value: str | None) -> str:
    """Mapuje ATOS avail atribut na standardní hodnoty."""
    if not avail_value:
        return "out_of_stock"

    avail_lower = avail_value.lower().strip()

    # Mapping podle reálných hodnot v ATOS XML
    if avail_lower in ["1", "yes", "true", "dostępny", "available"]:
        return "in_stock"
    elif avail_lower in ["0", "no", "false", "niedostępny", "unavailable"]:
        return "out_of_stock"
    elif "preorder" in avail_lower or "przedsprzedaż" in avail_lower:
        return "preorder"
    else:
        # Default fallback
        return "out_of_stock"


def _parse_stock(stock_str: str | None) -> int:
    """Parsuje stock jako int, fallback 0."""
    if not stock_str:
        return 0
    try:
        return int(stock_str)
    except (ValueError, TypeError):
        return 0


def _parse_price(price_str: str | None) -> Decimal:
    """Parsuje cenu jako Decimal."""
    if not price_str:
        return Decimal("0")
    try:
        # Replace comma with dot for decimal separator
        price_clean = price_str.replace(',', '.')
        return Decimal(price_clean)
    except Exception:
        return Decimal("0")


def _parse_images(imgs_element) -> list[ImageRaw]:
    """Parsuje obrázky z <imgs> elementu.

    Skutečná struktura ATOS XML:
      <imgs>
        <main url="https://hurtmeble.eu/.../export.jpg"/>   ← hlavní
        <i url="https://hurtmeble.eu/.../export.jpg"/>       ← ostatní
      </imgs>

    URL je atribut, ne textový obsah elementu.
    """
    if imgs_element is None:
        return []

    images = []

    # Hlavní obrázek: <main url="..."/>
    main_el = imgs_element.find('main')
    if main_el is not None:
        url = main_el.get('url', '').strip()
        if url:
            images.append(ImageRaw(url=url, is_main=True))

    # Ostatní obrázky: <i url="..."/>
    for i_el in imgs_element.findall('i'):
        url = i_el.get('url', '').strip()
        if url:
            images.append(ImageRaw(url=url, is_main=False))

    return images


def _classify_attributes(attrs_element, config: dict) -> list[ParsedAttribute]:
    """Klasifikuje atributy jako variantní nebo parametrické podle whitelistu.

    Skutečná struktura ATOS XML:
    <attrs>
        <a name="Kolor">1 MIKROFAZA</a>
        <a name="Waga [kg]">12</a>
        ...
    </attrs>
    """
    if attrs_element is None:
        return []

    variant_whitelist = config.get('variant_attribute_whitelist', [])
    parameter_whitelist = config.get('parameter_attribute_whitelist', [])

    result = []

    # Parsuj <a> elementy přímo (ne vnořené v <attr>)
    for a_elem in attrs_element.findall('a'):
        attr_name = a_elem.get('name', '').strip()
        attr_value = (a_elem.text or '').strip()

        if not attr_name or not attr_value:
            continue

        # Klasifikace: variantní pokud v variant_whitelist, jinak parametrický (default safe)
        is_variant = attr_name in variant_whitelist

        result.append(ParsedAttribute(
            name_pl=attr_name,
            values_pl=[attr_value],  # V této struktuře každý atribut má jednu hodnotu
            is_variant=is_variant
        ))

    return result


def parse(xml_path: str, category_filter: str | None = None) -> list[ParsedProduct]:
    """Parsuje ATOS XML a vrací list ParsedProduct.

    Args:
        xml_path: Cesta k ATOS XML souboru
        category_filter: Volitelný filtr kategorie (case-insensitive substring match)

    Returns:
        List ParsedProduct, seřazeno podle item_group_key

    Raises:
        ValueError: Pokud XML není parseable nebo 0 offerů po filtru
    """
    config = _load_config()
    ean_regex = config['ean_extraction']['regex']

    # Parse XML pomocí lxml iterparse pro stream parsing (46MB soubor)
    try:
        context = etree.iterparse(xml_path, events=('end',), tag='o')
    except Exception as e:
        raise ValueError(f"XML není parseable: {e}")

    offers_by_group: dict[str, list[ParsedOffer]] = {}

    for event, elem in context:
        # Extrahuj základní data z <o> elementu
        offer_id = elem.get('id', '').strip()
        price_str = elem.get('price', '')
        stock_str = elem.get('stock', '')
        avail_str = elem.get('avail', '')
        url = elem.get('url', '').strip()

        # Extrahuj vnořené elementy
        name = elem.findtext('name', '').strip()
        cat = elem.findtext('cat', '').strip()
        desc = elem.findtext('desc', '').strip()
        symbol = elem.findtext('symbol', '').strip() or None

        # Normalizuj kategorii
        cat_normalized = _normalize_category(cat)

        # Category filter
        if category_filter and category_filter.lower() not in cat_normalized.lower():
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            continue

        # Parse cat_path
        cat_path = [seg.strip() for seg in cat_normalized.split('/') if seg.strip()]

        # item_group_key = cat_path[1] (druhý segment = název produktu)
        # Edge case: pokud len(cat_path) < 2, fallback na cat_path[0]
        if len(cat_path) >= 2:
            item_group_key = cat_path[1]
        else:
            item_group_key = cat_path[0] if cat_path else 'unknown'

        # subcategory_pl = cat_path[2] pokud existuje (materiálová podkategorie)
        subcategory_pl = cat_path[2] if len(cat_path) > 2 else None

        # Parse price, stock, avail
        price_pln = _parse_price(price_str)
        stock = _parse_stock(stock_str)
        avail = _map_avail(avail_str)

        # EAN extraction
        ean = _extract_ean(url, ean_regex) if url else None

        # Images — <imgs><main url="..."/><i url="..."/></imgs>
        imgs_elem = elem.find('imgs')
        images = _parse_images(imgs_elem)

        # Attributes
        attrs_elem = elem.find('attrs')
        attributes = _classify_attributes(attrs_elem, config)

        # Vytvoř ParsedOffer
        offer = ParsedOffer(
            id=offer_id,
            name_pl=name,
            cat_pl=cat_normalized,
            cat_path_pl=cat_path,
            desc_pl=desc,
            price_pln=price_pln,
            stock=stock,
            avail=avail,
            url=url,
            symbol=symbol,
            ean=ean,
            images=images,
            attributes=attributes,
            item_group_key=item_group_key,
            subcategory_pl=subcategory_pl
        )

        # Group by item_group_key
        if item_group_key not in offers_by_group:
            offers_by_group[item_group_key] = []
        offers_by_group[item_group_key].append(offer)

        # Cleanup pro memory efficiency
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    # Cleanup context
    del context

    # Check pokud 0 offers
    if not offers_by_group:
        raise ValueError("0 offerů po filtru")

    # Vytvoř ParsedProduct z groups
    products = []
    for group_key, offers in offers_by_group.items():
        # cat_path_pl = cat_path[:2] = [kategorie zbozi, nazev produktu]
        # Použijeme cat_path_pl z prvního offeru
        first_cat_path = offers[0].cat_path_pl
        common_cat_path = first_cat_path[:2] if len(first_cat_path) >= 2 else first_cat_path

        product = ParsedProduct(
            item_group_key=group_key,
            cat_path_pl=common_cat_path,
            offers=offers
        )
        products.append(product)

    # Seřaď podle item_group_key
    products.sort(key=lambda p: p.item_group_key)

    return products
