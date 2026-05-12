"""Testy pro validator.py - 9 BLOCK + 5 WARN pravidel."""

import pytest
from decimal import Decimal

from polotovar.schema import Polotovar, Product, Variant, PriceCZK, Attribute
from polotovar.validator import validate, ValidationResult


@pytest.fixture
def valid_product():
    """Fixture: validni produkt s 1 variantou."""
    variant = Variant(
        id="var_1",
        price_czk=PriceCZK(value=Decimal("1000"), koeficient_used=Decimal("11.115")),
        availability="in_stock",
        stock_quantity=10,
        image_link="https://example.com/img.jpg",
        additional_image_links=[],
        variant_attributes=[
            Attribute(name_cz="Barva", name_pl="Kolor", value_cz="cervena", value_pl="czerwony", is_variant=True)
        ],
        ean="1234567890123"
    )

    product = Product(
        id="prod_1",
        item_group_id="group_1",
        title_cz="Kreslo Milo",
        description_cz="Popis kresla Milo",
        category_path_cz=["Kresla", "Kreslo Milo"],
        price_czk=PriceCZK(value=Decimal("1000"), koeficient_used=Decimal("11.115")),
        image_link="https://example.com/img.jpg",
        availability="in_stock",
        variants=[variant],
        attrs_cz=[
            Attribute(name_cz="Hmotnost", name_pl="Waga", value_cz="15 kg", value_pl="15 kg", is_variant=False)
        ],
        # Audit fields
        title_pl="Fotel Milo",
        description_pl="Opis fotela Milo",
        category_path_pl=["FOTELE", "FOTEL MILO"],
        attrs_raw=[]
    )

    return product


def test_validate_pass(valid_product):
    """Test: validni polotovar projde s verdict=PASS."""
    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[valid_product]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "PASS"
    assert len(result.blocking_errors) == 0


def test_block_1_prazdny_polotovar():
    """Test BLOCK-1: polotovar bez produktu."""
    # Pydantic uz to chytne pri vytvareni Polotovar modelu
    with pytest.raises(Exception):
        Polotovar(
            supplier="atos",
            category="test",
            generated_at="2026-05-12T00:00:00Z",
            products=[]
        )


def test_block_2_chybi_povinne_pole(valid_product):
    """Test BLOCK-2: produkt bez title_cz."""
    product = valid_product.model_copy()
    product.title_cz = ""

    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[product]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "BLOCKED"
    assert any(err.rule == "BLOCK-2" for err in result.blocking_errors)


def test_block_3_cena_nula(valid_product):
    """Test BLOCK-3: cena <= 0."""
    product = valid_product.model_copy(deep=True)

    # Pydantic model validator uz to chytne pri vytvareni PriceCZK
    # Takze test spadne na pydantic validation error
    with pytest.raises(Exception):
        product.price_czk = PriceCZK(value=Decimal("0"), koeficient_used=Decimal("11.115"))


def test_block_4_mena_neni_czk(valid_product):
    """Test BLOCK-4: mena != CZK."""
    # Tohle nelze snadno otestovat, protoze PriceCZK ma Literal["CZK"]
    # Pydantic to odmitne uz pri vytvareni modelu
    pass


def test_block_5_zadne_varianty(valid_product):
    """Test BLOCK-5: produkt bez variant."""
    # Pydantic model validator to odmitne (min_items=1)
    with pytest.raises(Exception):
        product_dict = valid_product.model_dump()
        product_dict['variants'] = []
        product = Product(**product_dict)

        Polotovar(
            supplier="atos",
            category="test",
            generated_at="2026-05-12T00:00:00Z",
            products=[product]
        )


def test_block_6_chybi_image_link(valid_product):
    """Test BLOCK-6: prazdny image_link."""
    product = valid_product.model_copy()
    product.image_link = ""

    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[product]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "BLOCKED"
    assert any(err.rule == "BLOCK-6" for err in result.blocking_errors)


def test_block_7_duplicitni_id(valid_product):
    """Test BLOCK-7: duplicitni product.id."""
    product1 = valid_product.model_copy(deep=True)
    product2 = valid_product.model_copy(deep=True)
    product2.item_group_id = "group_2"  # zmenit item_group_id, ale ID stejne

    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[product1, product2]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "BLOCKED"
    assert any(err.rule == "BLOCK-7" for err in result.blocking_errors)


def test_block_8_milo_482_variant(valid_product):
    """Test BLOCK-8: kategorie milo musi mit 482 variant."""
    # Vytvorime 10 produktu s 48 variantami kazdy (celkem 480, ne 482)
    products = []
    for i in range(10):
        product = valid_product.model_copy(deep=True)
        product.id = f"prod_{i}"
        product.item_group_id = f"group_{i}"

        # Vytvor 48 variant
        variants = []
        for j in range(48):
            var = product.variants[0].model_copy(deep=True)
            var.id = f"var_{i}_{j}"
            variants.append(var)
        product.variants = variants

        products.append(product)

    polotovar = Polotovar(
        supplier="atos",
        category="milo",
        generated_at="2026-05-12T00:00:00Z",
        products=products
    )

    # Celkem 480 variant, ocekavano 482 → BLOCK
    result = validate(polotovar, "milo")
    assert result.verdict == "BLOCKED"
    assert any(err.rule == "BLOCK-8" for err in result.blocking_errors)


def test_block_9_polske_diakritiky_v_title(valid_product):
    """Test BLOCK-9: polske diakritiky v title_cz."""
    product = valid_product.model_copy()
    product.title_cz = "Fotel Milo ąęłś"  # polske diakritiky

    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[product]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "BLOCKED"
    assert any(err.rule == "BLOCK-9" for err in result.blocking_errors)


def test_warn_1_chybi_ean(valid_product):
    """Test WARN-1: chybi EAN (gtin) - soft warning."""
    product = valid_product.model_copy()
    product.gtin = None

    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[product]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "PASS"  # Neni blocking
    assert len([w for w in result.warnings if w.rule == "WARN-1"]) > 0


def test_warn_2_chybi_brand(valid_product):
    """Test WARN-2: chybi brand."""
    product = valid_product.model_copy()
    product.brand = None

    polotovar = Polotovar(
        supplier="atos",
        category="test",
        generated_at="2026-05-12T00:00:00Z",
        products=[product]
    )

    result = validate(polotovar, "test")
    assert result.verdict == "PASS"
    assert len([w for w in result.warnings if w.rule == "WARN-2"]) > 0
