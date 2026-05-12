"""Testy pro schema.py - pydantic modely."""

import pytest
from decimal import Decimal

from polotovar.schema import (
    PriceCZK,
    Image,
    Attribute,
    Variant,
    Product,
    Polotovar
)


def test_price_czk_valid():
    """Test: PriceCZK s validni hodnotou."""
    price = PriceCZK(
        value=Decimal("1000.50"),
        koeficient_used=Decimal("11.115"),
        override_applied=False
    )
    assert price.value == Decimal("1000.50")
    assert price.currency == "CZK"
    assert price.koeficient_used == Decimal("11.115")
    assert price.override_applied is False


def test_price_czk_value_must_be_positive():
    """Test: PriceCZK value musi byt > 0."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        PriceCZK(
            value=Decimal("0"),  # Invalid: <= 0
            koeficient_used=Decimal("11.115")
        )


def test_image():
    """Test: Image model."""
    img = Image(url="https://example.com/img.jpg", is_main=True)
    assert img.url == "https://example.com/img.jpg"
    assert img.is_main is True


def test_attribute():
    """Test: Attribute model."""
    attr = Attribute(
        name_cz="Barva",
        name_pl="Kolor",
        value_cz="cervena",
        value_pl="czerwony",
        is_variant=True
    )
    assert attr.name_cz == "Barva"
    assert attr.is_variant is True


def test_variant():
    """Test: Variant model."""
    price = PriceCZK(value=Decimal("500"), koeficient_used=Decimal("11.115"))
    attr = Attribute(
        name_cz="Barva",
        name_pl="Kolor",
        value_cz="cervena",
        value_pl="czerwony",
        is_variant=True
    )

    variant = Variant(
        id="var_1",
        price_czk=price,
        availability="in_stock",
        stock_quantity=10,
        image_link="https://example.com/img.jpg",
        variant_attributes=[attr]
    )

    assert variant.id == "var_1"
    assert variant.availability == "in_stock"
    assert len(variant.variant_attributes) == 1


def test_product():
    """Test: Product model."""
    price = PriceCZK(value=Decimal("1000"), koeficient_used=Decimal("11.115"))
    variant = Variant(
        id="var_1",
        price_czk=price,
        availability="in_stock",
        stock_quantity=10,
        image_link="https://example.com/img.jpg",
        variant_attributes=[]
    )

    product = Product(
        id="prod_1",
        item_group_id="group_1",
        title_cz="Kreslo Milo",
        description_cz="Popis",
        category_path_cz=["Kresla", "Kreslo Milo"],
        price_czk=price,
        image_link="https://example.com/img.jpg",
        availability="in_stock",
        variants=[variant],
        attrs_cz=[],
        # Audit fields
        title_pl="Fotel Milo",
        description_pl="Opis",
        category_path_pl=["FOTELE", "FOTEL MILO"],
        attrs_raw=[]
    )

    assert product.id == "prod_1"
    assert len(product.variants) == 1


def test_product_must_have_variants():
    """Test: Product musi mit aspon 1 variantu."""
    price = PriceCZK(value=Decimal("1000"), koeficient_used=Decimal("11.115"))

    with pytest.raises(Exception):  # Pydantic ValidationError
        Product(
            id="prod_1",
            item_group_id="group_1",
            title_cz="Kreslo Milo",
            description_cz="Popis",
            category_path_cz=["Kresla"],
            price_czk=price,
            image_link="https://example.com/img.jpg",
            availability="in_stock",
            variants=[],  # Invalid: prazdne varianty
            attrs_cz=[],
            title_pl="Fotel Milo",
            description_pl="Opis",
            category_path_pl=["FOTELE"],
            attrs_raw=[]
        )


def test_polotovar():
    """Test: Polotovar model."""
    price = PriceCZK(value=Decimal("1000"), koeficient_used=Decimal("11.115"))
    variant = Variant(
        id="var_1",
        price_czk=price,
        availability="in_stock",
        stock_quantity=10,
        image_link="https://example.com/img.jpg",
        variant_attributes=[]
    )
    product = Product(
        id="prod_1",
        item_group_id="group_1",
        title_cz="Kreslo Milo",
        description_cz="Popis",
        category_path_cz=["Kresla"],
        price_czk=price,
        image_link="https://example.com/img.jpg",
        availability="in_stock",
        variants=[variant],
        attrs_cz=[],
        title_pl="Fotel Milo",
        description_pl="Opis",
        category_path_pl=["FOTELE"],
        attrs_raw=[]
    )

    polotovar = Polotovar(
        supplier="atos",
        category="milo",
        generated_at="2026-05-12T00:00:00Z",
        products=[product]
    )

    assert polotovar.supplier == "atos"
    assert polotovar.schema_version == "2.0"
    assert len(polotovar.products) == 1


def test_polotovar_must_have_products():
    """Test: Polotovar musi mit aspon 1 produkt."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        Polotovar(
            supplier="atos",
            category="milo",
            generated_at="2026-05-12T00:00:00Z",
            products=[]
        )
