"""Merge variant na master produkty.

Bere List[ParsedProduct] z parseru a vraci List[Product] (pydantic schema).

Logika:
- Master produkt = item_group_key (napr. "FOTEL MILO")
- Varianty = N offeru se stejnym item_group_key
- Variantni atributy: hardcoded whitelist {Kolor, Materiał}
- Parametricke atributy: vsechno ostatni (Rozmery, Hmotnost, Kod_producenta, Producent)
- Master cena = nejnizsi cena z variant
- Master image_link = prvni varianta s main=1 v imgs
- Master availability = in_stock pokud aspon 1 varianta in_stock
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from decimal import Decimal
from typing import List
from polotovar.parser_atos import ParsedProduct, ParsedOffer
from polotovar.schema import Product, Variant, PriceCZK, Image, Attribute
from polotovar.translator import (
    load_slovnik,
    translate_attribute_name,
    translate_attribute_value,
    translate_category_segment
)
from polotovar.pricing import convert_pln_to_czk, OverrideRow


# Hardcoded whitelist variantnich atributu (PL nazvy)
VARIANT_ATTR_WHITELIST = {"Kolor", "Materiał"}


def _collect_parametric_attrs(
    offers: List[ParsedOffer],
    slovnik: dict,
    kategorie_context: str
) -> List[Attribute]:
    """Vybere parametricke atributy (spolecne pro vsechny varianty).

    Parametricke = vsechny atributy MIMO VARIANT_ATTR_WHITELIST.
    Bere z prvniho offeru (predpokladame, ze jsou stejne pro vsechny varianty).
    """
    if not offers:
        return []

    first_offer = offers[0]
    parametric = []

    for attr in first_offer.attributes:
        if attr.name_pl not in VARIANT_ATTR_WHITELIST:
            # Preloz nazev a hodnotu
            name_cz = translate_attribute_name(attr.name_pl, slovnik, kategorie_context)
            # Hodnota: vezmi prvni hodnotu z values_pl
            value_pl = attr.values_pl[0] if attr.values_pl else ""
            value_cz = translate_attribute_value(value_pl, slovnik)

            parametric.append(Attribute(
                name_cz=name_cz,
                name_pl=attr.name_pl,
                value_cz=value_cz,
                value_pl=value_pl,
                is_variant=False
            ))

    return parametric


def _build_variant(
    offer: ParsedOffer,
    overrides: dict[str, OverrideRow],
    slovnik: dict,
    kategorie_context: str
) -> Variant:
    """Vytvori Variant objekt z ParsedOffer."""
    # Konverze ceny PLN → CZK
    price_result = convert_pln_to_czk(offer.price_pln, offer.id, overrides)
    price_czk = PriceCZK(
        value=price_result.value,
        currency="CZK",
        koeficient_used=price_result.koeficient_used,
        override_applied=price_result.override_applied
    )

    # Image link (prvni obrazek, pokud existuje)
    # POZOR: image_link je MIN field, takze musi byt neprazdny
    # Pokud offer nema obrazek, pouzijeme placeholder
    if offer.images and offer.images[0].url:
        image_link = offer.images[0].url
    else:
        # Fallback: placeholder (validator to chytne jako blocking pokud je prazdny)
        image_link = "https://placeholder.com/missing-image.jpg"

    # Additional images
    additional_images = [
        Image(url=img.url, is_main=img.is_main)
        for img in offer.images[1:]  # skip prvni (uz je v image_link)
    ]

    # Variantni atributy
    variant_attrs = []
    for attr in offer.attributes:
        if attr.name_pl in VARIANT_ATTR_WHITELIST:
            name_cz = translate_attribute_name(attr.name_pl, slovnik, kategorie_context)
            value_pl = attr.values_pl[0] if attr.values_pl else ""
            value_cz = translate_attribute_value(value_pl, slovnik)

            variant_attrs.append(Attribute(
                name_cz=name_cz,
                name_pl=attr.name_pl,
                value_cz=value_cz,
                value_pl=value_pl,
                is_variant=True
            ))

    return Variant(
        id=offer.id,
        price_czk=price_czk,
        availability=offer.avail,
        stock_quantity=offer.stock,
        image_link=image_link,
        additional_image_links=additional_images,
        variant_attributes=variant_attrs,
        ean=offer.ean,
        url=offer.url
    )


def merge_variants(
    parsed_products: List[ParsedProduct],
    slovnik_path: str,
    overrides: dict[str, OverrideRow]
) -> List[Product]:
    """Slouceni variant na master produkty.

    Args:
        parsed_products: Vystup z parser_atos.parse()
        slovnik_path: Cesta ke slovniku
        overrides: dict overridu z pricing.load_overrides()

    Returns:
        List[Product] s pydantic schema
    """
    slovnik = load_slovnik(slovnik_path)
    products = []

    for parsed in parsed_products:
        # Kategorialni kontext pro per-kategorii override
        kategorie_context = parsed.cat_path_pl[0] if parsed.cat_path_pl else None

        # Preloz kategorii
        category_path_cz = [
            translate_category_segment(seg, slovnik)
            for seg in parsed.cat_path_pl
        ]

        # Parametricke atributy (spolecne)
        attrs_cz = _collect_parametric_attrs(parsed.offers, slovnik, kategorie_context)

        # Vytvor varianty
        variants = [
            _build_variant(offer, overrides, slovnik, kategorie_context)
            for offer in parsed.offers
        ]

        # Master cena = nejnizsi z variant
        if not variants:
            continue  # skip produkty bez variant

        min_variant = min(variants, key=lambda v: v.price_czk.value)
        master_price_czk = min_variant.price_czk

        # Master image_link = prvni varianta s main=1, fallback prvni varianta
        master_image_link = ""
        for v in variants:
            if v.image_link:
                master_image_link = v.image_link
                # Check jestli ma main=1 (v additional_image_links)
                for img in v.additional_image_links:
                    if img.is_main:
                        master_image_link = img.url
                        break
                if master_image_link:
                    break

        # Master availability = in_stock pokud aspon 1 varianta in_stock
        master_availability = "out_of_stock"
        for v in variants:
            if v.availability == "in_stock":
                master_availability = "in_stock"
                break
        # Pokud zadna neni in_stock, vezmi availability z prvni varianty
        if master_availability == "out_of_stock" and variants:
            master_availability = variants[0].availability

        # Master title, description (preloz z prvniho offeru)
        first_offer = parsed.offers[0]
        title_cz = translate_category_segment(parsed.item_group_key, slovnik)
        description_cz = first_offer.desc_pl  # TODO: prelozit pres slovnik nebo fallback
        # Pro MVP pouzijeme PL popis (zatim neni v slovniku)
        # Validator BLOCK-9 to chytne pokud ma polske diakritiky

        # Master ID = item_group_id = item_group_key
        product_id = parsed.item_group_key
        item_group_id = parsed.item_group_key

        # attrs_raw (audit)
        attrs_raw = [
            {
                'name_pl': attr.name_pl,
                'values_pl': attr.values_pl,
                'is_variant': attr.is_variant
            }
            for attr in first_offer.attributes
        ]

        # Vytvor Product
        product = Product(
            id=product_id,
            item_group_id=item_group_id,
            title_cz=title_cz,
            description_cz=description_cz,
            category_path_cz=category_path_cz,
            price_czk=master_price_czk,
            image_link=master_image_link,
            availability=master_availability,
            variants=variants,
            attrs_cz=attrs_cz,
            # OPT fields
            brand=None,  # TODO: extract z attributes pokud existuje "Producent"
            gtin=None,
            dimensions=None,  # TODO: extract z attributes pokud existuje
            weight_kg=None,
            color=None,
            material=None,
            additional_image_links=[],
            # Audit fields
            title_pl=first_offer.name_pl,
            description_pl=first_offer.desc_pl,
            category_path_pl=parsed.cat_path_pl,
            attrs_raw=attrs_raw
        )

        products.append(product)

    return products
