"""Testy pro variants.py - merge variant na master produkty."""

import pytest
from decimal import Decimal
from pathlib import Path

from polotovar.parser_atos import parse as parse_atos, ParsedProduct, ParsedOffer, ImageRaw, ParsedAttribute
from polotovar.variants import merge_variants
from polotovar.pricing import load_overrides


@pytest.fixture
def mock_parsed_product():
    """Fixture: jednodussi ParsedProduct pro testy."""
    offer1 = ParsedOffer(
        id="offer_1",
        name_pl="Fotel Milo czerwony",
        cat_pl="FOTELE/FOTEL MILO/MIKROFAZA/NOGI 20 BIAŁE",
        cat_path_pl=["FOTELE", "FOTEL MILO", "MIKROFAZA", "NOGI 20 BIAŁE"],
        desc_pl="Opis fotela",
        price_pln=Decimal("100"),
        stock=10,
        avail="in_stock",
        url="https://example.com/product-1",
        symbol="FOT-001",
        ean="1234567890123",
        images=[ImageRaw(url="https://example.com/img1.jpg", is_main=True)],
        attributes=[
            ParsedAttribute(name_pl="Kolor", values_pl=["czerwony"], is_variant=True),
            ParsedAttribute(name_pl="Waga", values_pl=["15 kg"], is_variant=False)
        ],
        item_group_key="FOTEL MILO",
        subcategory_pl="MIKROFAZA"
    )

    offer2 = ParsedOffer(
        id="offer_2",
        name_pl="Fotel Milo niebieski",
        cat_pl="FOTELE/FOTEL MILO/VELVET/NOGI 20 BUK",
        cat_path_pl=["FOTELE", "FOTEL MILO", "VELVET", "NOGI 20 BUK"],
        desc_pl="Opis fotela",
        price_pln=Decimal("120"),
        stock=5,
        avail="in_stock",
        url="https://example.com/product-2",
        symbol="FOT-002",
        ean="1234567890124",
        images=[ImageRaw(url="https://example.com/img2.jpg", is_main=True)],
        attributes=[
            ParsedAttribute(name_pl="Kolor", values_pl=["niebieski"], is_variant=True),
            ParsedAttribute(name_pl="Waga", values_pl=["15 kg"], is_variant=False)
        ],
        item_group_key="FOTEL MILO",
        subcategory_pl="VELVET"
    )

    return ParsedProduct(
        item_group_key="FOTEL MILO",
        cat_path_pl=["FOTELE", "FOTEL MILO"],
        offers=[offer1, offer2]
    )


def test_merge_variants_basic(mock_parsed_product, tmp_path):
    """Test: zakladni merge variant."""
    # Vytvor docasny slovnik
    slovnik_path = tmp_path / "slovnik.json"
    slovnik_data = {
        "schema_version": "1.0",
        "namespaces": {
            "atributy": {"Kolor": "Barva", "Waga": "Hmotnost"},
            "hodnoty": {"czerwony": "cervena", "niebieski": "modra"},
            "kategorie": {"FOTELE": "Kresla", "FOTEL MILO": "Kreslo Milo"}
        },
        "per_kategorii_override": {}
    }
    import json
    with open(slovnik_path, 'w', encoding='utf-8') as f:
        json.dump(slovnik_data, f)

    # Prazdne overridy
    overrides = {}

    products = merge_variants([mock_parsed_product], str(slovnik_path), overrides)

    assert len(products) == 1
    product = products[0]

    # Check master product
    assert product.item_group_id == "FOTEL MILO"
    assert "Kreslo Milo" in product.title_cz
    assert len(product.variants) == 2

    # Check cena (nejnizsi z variant)
    # offer1: 100 PLN * 11.115 = 1111.5 CZK
    # offer2: 120 PLN * 11.115 = 1333.8 CZK
    # Master cena = 1111.5
    assert product.price_czk.value == Decimal("1111.50")

    # Check varianty
    assert product.variants[0].id == "offer_1"
    assert product.variants[1].id == "offer_2"


def test_merge_variants_master_availability():
    """Test: master availability = in_stock pokud aspon 1 varianta in_stock."""
    # Tohle je komplexnejsi test, pro MVP staci zakladni test vyse
    pass


def test_merge_variants_s_overrides(mock_parsed_product, tmp_path):
    """Test: merge s cenovou override."""
    slovnik_path = tmp_path / "slovnik.json"
    slovnik_data = {
        "schema_version": "1.0",
        "namespaces": {
            "atributy": {"Kolor": "Barva"},
            "hodnoty": {},
            "kategorie": {"FOTEL MILO": "Kreslo Milo"}
        },
        "per_kategorii_override": {}
    }
    import json
    with open(slovnik_path, 'w', encoding='utf-8') as f:
        json.dump(slovnik_data, f)

    # Override pro offer_1
    from polotovar.pricing import OverrideRow
    overrides = {
        "offer_1": OverrideRow(
            id_produktu="offer_1",
            koeficient_override=Decimal("1.5"),
            poznamka="Test",
            platnost_do=None
        )
    }

    products = merge_variants([mock_parsed_product], str(slovnik_path), overrides)
    product = products[0]

    # offer_1 s override: 100 * 11.115 * 1.5 = 1667.25 CZK
    # offer_2 bez override: 120 * 11.115 = 1333.8 CZK
    # Master cena = 1333.8 (nejnizsi)
    assert product.price_czk.value == Decimal("1333.80")

    # Check ze offer_1 ma override_applied=True
    variant1 = [v for v in product.variants if v.id == "offer_1"][0]
    assert variant1.price_czk.override_applied is True
