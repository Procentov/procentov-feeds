"""Testy pro parser_atos.py"""
from pathlib import Path
from decimal import Decimal
import pytest
from polotovar.parser_atos import parse, ParsedProduct, ParsedOffer


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "atos_milo_sample.xml"


def test_parses_milo_fixture():
    """Parse fixture vrací > 0 produktů."""
    result = parse(str(FIXTURE_PATH), "FOTEL MILO")
    assert len(result) > 0, "Parser musí vrátit alespoň 1 produkt"


def test_total_offers_count():
    """Součet offers napříč všemi produkty >= 348."""
    result = parse(str(FIXTURE_PATH), "MILO")
    total_offers = sum(len(p.offers) for p in result)
    assert total_offers >= 348, f"Očekáváno ≥ 348 offers, získáno {total_offers}"


def test_master_count_reasonable():
    """Počet master produktů mezi 1 a 5 (realita pro Milo: 2)."""
    result = parse(str(FIXTURE_PATH), "MILO")
    count = len(result)
    assert 1 <= count <= 5, f"Očekáváno 1-5 master produktů, získáno {count}"


def test_ean_extraction():
    """Alespoň 80 % offerů má ean != None."""
    result = parse(str(FIXTURE_PATH), "MILO")
    total_offers = sum(len(p.offers) for p in result)
    offers_with_ean = sum(
        1 for p in result for offer in p.offers if offer.ean is not None
    )

    percentage = (offers_with_ean / total_offers) * 100 if total_offers > 0 else 0
    assert percentage >= 80, f"Očekáváno ≥ 80% offers s EAN, získáno {percentage:.1f}%"


def test_attribute_classification():
    """Existuje offer s variantním atributem a offer s parametrickým atributem."""
    result = parse(str(FIXTURE_PATH), "MILO")

    has_variant = False
    has_parameter = False

    for product in result:
        for offer in product.offers:
            for attr in offer.attributes:
                if attr.is_variant:
                    has_variant = True
                else:
                    has_parameter = True

            if has_variant and has_parameter:
                break
        if has_variant and has_parameter:
            break

    assert has_variant, "Neexistuje žádný variantní atribut (Kolor/Materiał)"
    assert has_parameter, "Neexistuje žádný parametrický atribut"


def test_category_filter_none():
    """Parse s filter=None vrací stejný počet jako filter='MILO' pro Milo-only fixture."""
    result_with_filter = parse(str(FIXTURE_PATH), "MILO")
    result_without_filter = parse(str(FIXTURE_PATH), None)

    total_with = sum(len(p.offers) for p in result_with_filter)
    total_without = sum(len(p.offers) for p in result_without_filter)

    assert total_with == total_without, \
        f"Filter=None by měl vrátit stejný počet jako filter='MILO' pro Milo fixture: {total_without} vs {total_with}"


def test_item_group_grouping():
    """Dva offery se stejným item_group_key jsou ve stejném ParsedProduct."""
    result = parse(str(FIXTURE_PATH), "MILO")

    # Najdeme produkt s více než 1 variantou
    multi_variant_product = None
    for product in result:
        if len(product.offers) > 1:
            multi_variant_product = product
            break

    assert multi_variant_product is not None, "Neexistuje produkt s více než 1 variantou"

    # Ověř, že všechny offery v tomto produktu mají stejný item_group_key
    first_key = multi_variant_product.offers[0].item_group_key
    for offer in multi_variant_product.offers:
        assert offer.item_group_key == first_key, \
            f"Offer {offer.id} má jiný item_group_key: {offer.item_group_key} vs {first_key}"


def test_price_is_decimal():
    """Ceny jsou typu Decimal, ne float."""
    result = parse(str(FIXTURE_PATH), "MILO")

    for product in result:
        for offer in product.offers:
            assert isinstance(offer.price_pln, Decimal), \
                f"Offer {offer.id} má cenu typu {type(offer.price_pln)}, očekáván Decimal"


def test_milo_has_exactly_two_masters():
    """Milo fixture musi dat presne 2 master produkty: FOTEL MILO + SOFA MILO."""
    result = parse(str(FIXTURE_PATH), "MILO")
    assert len(result) == 2, f"Očekáváno 2 master produkty, získáno {len(result)}"
    keys = sorted(p.item_group_key for p in result)
    assert keys == ["FOTEL MILO", "SOFA MILO"], f"Očekávány klíče ['FOTEL MILO', 'SOFA MILO'], získáno {keys}"


def test_no_material_split():
    """Nabidky z Velvet, Ekokuze (Eco Skora), Mikrofaza musi byt pod stejnym master,
    NE v separatnich ParsedProduct."""
    result = parse(str(FIXTURE_PATH), "MILO")
    fotel_milos = [p for p in result if p.item_group_key == "FOTEL MILO"]
    assert len(fotel_milos) == 1, "FOTEL MILO musi byt jeden master, ne rozsekany podle materialu"

    # Overit, ze pod tim jednim masterem mame nabidky vsech 3 materialu
    subcats = {o.subcategory_pl for o in fotel_milos[0].offers if o.subcategory_pl}
    assert len(subcats) >= 3, f"Ocekavany >=3 ruzne subcategory (materialy), nasel {len(subcats)}: {subcats}"


def test_cat_path_pl_is_two_segments():
    """ParsedProduct.cat_path_pl musi mit 2 segmenty: [kategorie, produkt]."""
    result = parse(str(FIXTURE_PATH), "MILO")
    for p in result:
        assert len(p.cat_path_pl) == 2, f"Ocekavany 2 segmenty, mam {len(p.cat_path_pl)}: {p.cat_path_pl}"


def test_subcategory_populated():
    """Vetsina Milo offers ma subcategory_pl populated (segment 2 existuje v <cat>)."""
    result = parse(str(FIXTURE_PATH), "MILO")
    total = sum(len(p.offers) for p in result)
    with_subcat = sum(1 for p in result for o in p.offers if o.subcategory_pl is not None)
    assert with_subcat / total >= 0.95, f"Pod 95% offers ma subcategory: {with_subcat}/{total}"
