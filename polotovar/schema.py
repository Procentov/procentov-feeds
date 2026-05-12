"""Pydantic v2 modely pro polotovar v2.0.

Schema definuje strukturu kanonického polotovaru:
- MIN pole = blocking (validator odmítne)
- OPT pole = warning (validator jen loguje)
- Audit fieldy (_pl, attrs_raw) = vždy zachovat pro debug
"""

import sys
# Windows fix: zajisti UTF-8 encoding pro stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from decimal import Decimal
from datetime import datetime


class PriceCZK(BaseModel):
    """Cena v CZK po aplikaci koeficientu a pripadnych overridu."""
    value: Decimal = Field(..., gt=0, description="MIN: > 0, blocking")
    currency: Literal["CZK"] = "CZK"
    koeficient_used: Decimal  # Audit: jaky koeficient byl pouzit (glob. nebo override)
    override_applied: bool = False  # Audit: byl pouzit override z CSV?


class Image(BaseModel):
    """Obrazek produktu."""
    url: str = Field(..., min_length=1)
    is_main: bool = False


class Attribute(BaseModel):
    """Variantni nebo parametricky atribut.

    Variantni = rozlisuji varianty (Barva, Material)
    Parametricky = spolecne pro vsechny varianty (Rozmery, Hmotnost)
    """
    name_cz: str = Field(..., min_length=1, description="MIN: blocking")
    name_pl: str  # Audit field
    value_cz: str = Field(..., min_length=1)
    value_pl: str  # Audit field
    is_variant: bool = Field(..., description="True = variantni, False = parametricky")


class Variant(BaseModel):
    """Jedna konkretni varianta produktu (napr. Kreslo Milo, barva cervena, material velvet)."""
    id: str = Field(..., min_length=1)
    price_czk: PriceCZK
    availability: Literal["in_stock", "out_of_stock", "preorder"]
    stock_quantity: Optional[int] = None
    image_link: str = Field(..., min_length=1, description="MIN: blocking")
    additional_image_links: List[Image] = []  # OPT
    variant_attributes: List[Attribute]  # Co rozlisuje variantu (Barva, Material)
    ean: Optional[str] = None  # OPT (rozhod. B z Discovery)
    url: Optional[str] = None  # Pro EAN extrakci a audit


class Product(BaseModel):
    """Master produkt s N variantami.

    Priklad: Master produkt "Kreslo Milo" ma 349 variant (ruzne barvy, materialy, nohy).
    """
    # MIN pole (blocking)
    id: str = Field(..., min_length=1)
    item_group_id: str = Field(..., min_length=1)
    title_cz: str = Field(..., min_length=1)
    description_cz: str = Field(..., min_length=1)
    category_path_cz: List[str] = Field(..., min_length=1)
    price_czk: PriceCZK  # Cena master produktu (nejnizsi z variant)
    image_link: str = Field(..., min_length=1)
    availability: Literal["in_stock", "out_of_stock", "preorder"]
    variants: List[Variant] = Field(..., min_length=1)
    attrs_cz: List[Attribute] = Field(..., description="Parametricke atributy spolecne pro vsechny varianty")

    # OPT pole (warning)
    brand: Optional[str] = None
    gtin: Optional[str] = None  # EAN master, OPT
    dimensions: Optional[str] = None
    weight_kg: Optional[Decimal] = None
    color: Optional[str] = None
    material: Optional[str] = None
    additional_image_links: List[Image] = []

    # Audit fields (vzdy zachovat)
    title_pl: str
    description_pl: str
    category_path_pl: List[str]
    attrs_raw: List[dict]  # Surova struktura z ATOS pro debug


class Polotovar(BaseModel):
    """Kanonicky polotovar pro jeden dodavatel x jednu kategorii."""
    supplier: Literal["atos", "art_decoration"]
    category: str  # napr. "milo"
    generated_at: str  # ISO 8601 timestamp
    schema_version: Literal["2.0"] = "2.0"
    products: List[Product] = Field(..., min_length=1)

    @field_validator("products")
    @classmethod
    def must_have_products(cls, v):
        """Validator: polotovar musi mit aspon 1 produkt."""
        if len(v) == 0:
            raise ValueError("Polotovar je prazdny - blocking")
        return v
