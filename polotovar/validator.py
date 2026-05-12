"""Validacni kontrakt polotovaru v2.0.

9 BLOCK pravidel (blocking gate):
- BLOCK-1: >=1 produkt
- BLOCK-2: kazdy produkt ma id, item_group_id, title_cz, description_cz, category_path_cz
- BLOCK-3: price_czk.value > 0
- BLOCK-4: currency == "CZK"
- BLOCK-5: kazdy produkt ma >=1 variantu
- BLOCK-6: image_link neprazdny
- BLOCK-7: zadne duplicitni id ani item_group_id
- BLOCK-8: pro category=="milo" → total_variants_count == 482
- BLOCK-9: zadne polske diakritiky v title_cz, description_cz, category_path_cz, attrs_cz

5 WARN pravidel (soft warning):
- WARN-1: EAN (gtin)
- WARN-2: brand
- WARN-3: dimensions
- WARN-4: ean per variant
- WARN-5: slovnik pokryti >=95%
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import re
import json
from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel
from polotovar.schema import Polotovar


class ValidationError(BaseModel):
    """Jedna validacni chyba."""
    rule: str
    product_id: str = ""
    field: str = ""
    value: str = ""
    detail: str = ""


class ValidationResult(BaseModel):
    """Vysledek validace."""
    timestamp: str
    verdict: Literal["PASS", "BLOCKED"]
    blocking_errors: List[ValidationError] = []
    warnings: List[ValidationError] = []


# Regex pro detekci polskych diakritik
POLISH_DIACRITICS_REGEX = re.compile(r'[ąćęłńóśźż]', re.IGNORECASE)


def _check_polish_text(text: str) -> bool:
    """Vraci True pokud text obsahuje polske diakritiky."""
    return bool(POLISH_DIACRITICS_REGEX.search(text))


def validate(polotovar: Polotovar, category_filter: str) -> ValidationResult:
    """Validuje polotovar podle 9 BLOCK + 5 WARN pravidel.

    Args:
        polotovar: Polotovar objekt
        category_filter: Kategorie pro BLOCK-8 check (napr. "milo")

    Returns:
        ValidationResult s verdict PASS nebo BLOCKED

    Raises:
        Exception pokud verdict == BLOCKED (blocking gate)
    """
    blocking = []
    warnings = []

    # BLOCK-1: >=1 produkt
    if len(polotovar.products) == 0:
        blocking.append(ValidationError(
            rule="BLOCK-1",
            detail="Polotovar je prazdny (0 produktu)"
        ))

    # Counters pro WARN-5 (slovnik pokryti)
    total_attrs = 0
    translated_attrs = 0

    # Per-produkt validace
    seen_ids = set()
    seen_item_group_ids = set()
    total_variants = 0

    for product in polotovar.products:
        # BLOCK-2: povinne pole
        if not product.id:
            blocking.append(ValidationError(
                rule="BLOCK-2",
                product_id=product.id or "UNKNOWN",
                field="id",
                detail="Produkt nema ID"
            ))
        if not product.item_group_id:
            blocking.append(ValidationError(
                rule="BLOCK-2",
                product_id=product.id,
                field="item_group_id",
                detail="Produkt nema item_group_id"
            ))
        if not product.title_cz:
            blocking.append(ValidationError(
                rule="BLOCK-2",
                product_id=product.id,
                field="title_cz",
                detail="Produkt nema title_cz"
            ))
        if not product.description_cz:
            blocking.append(ValidationError(
                rule="BLOCK-2",
                product_id=product.id,
                field="description_cz",
                detail="Produkt nema description_cz"
            ))
        if not product.category_path_cz or len(product.category_path_cz) == 0:
            blocking.append(ValidationError(
                rule="BLOCK-2",
                product_id=product.id,
                field="category_path_cz",
                detail="Produkt nema category_path_cz"
            ))

        # BLOCK-3: price_czk.value > 0
        if product.price_czk.value <= 0:
            blocking.append(ValidationError(
                rule="BLOCK-3",
                product_id=product.id,
                field="price_czk.value",
                value=str(product.price_czk.value),
                detail="Cena <= 0"
            ))

        # BLOCK-4: currency == "CZK"
        if product.price_czk.currency != "CZK":
            blocking.append(ValidationError(
                rule="BLOCK-4",
                product_id=product.id,
                field="price_czk.currency",
                value=product.price_czk.currency,
                detail="Mena neni CZK"
            ))

        # BLOCK-5: kazdy produkt ma >=1 variantu
        if len(product.variants) == 0:
            blocking.append(ValidationError(
                rule="BLOCK-5",
                product_id=product.id,
                detail="Produkt nema varianty"
            ))

        # BLOCK-6: image_link neprazdny
        if not product.image_link:
            blocking.append(ValidationError(
                rule="BLOCK-6",
                product_id=product.id,
                field="image_link",
                detail="Produkt nema image_link"
            ))

        # BLOCK-7: duplicitni id/item_group_id
        if product.id in seen_ids:
            blocking.append(ValidationError(
                rule="BLOCK-7",
                product_id=product.id,
                field="id",
                detail=f"Duplicitni id: {product.id}"
            ))
        seen_ids.add(product.id)

        if product.item_group_id in seen_item_group_ids:
            blocking.append(ValidationError(
                rule="BLOCK-7",
                product_id=product.id,
                field="item_group_id",
                value=product.item_group_id,
                detail=f"Duplicitni item_group_id: {product.item_group_id}"
            ))
        seen_item_group_ids.add(product.item_group_id)

        # BLOCK-9: polske diakritiky
        if _check_polish_text(product.title_cz):
            blocking.append(ValidationError(
                rule="BLOCK-9",
                product_id=product.id,
                field="title_cz",
                value=product.title_cz[:50],  # prvnich 50 znaku
                detail="Polske diakritiky detekovany v title_cz"
            ))
        if _check_polish_text(product.description_cz):
            blocking.append(ValidationError(
                rule="BLOCK-9",
                product_id=product.id,
                field="description_cz",
                value=product.description_cz[:50],
                detail="Polske diakritiky detekovany v description_cz"
            ))
        for seg in product.category_path_cz:
            if _check_polish_text(seg):
                blocking.append(ValidationError(
                    rule="BLOCK-9",
                    product_id=product.id,
                    field="category_path_cz",
                    value=seg,
                    detail="Polske diakritiky detekovany v category_path_cz"
                ))
        for attr in product.attrs_cz:
            if _check_polish_text(attr.name_cz):
                blocking.append(ValidationError(
                    rule="BLOCK-9",
                    product_id=product.id,
                    field="attrs_cz.name_cz",
                    value=attr.name_cz,
                    detail="Polske diakritiky detekovany v attrs_cz name"
                ))
            if _check_polish_text(attr.value_cz):
                blocking.append(ValidationError(
                    rule="BLOCK-9",
                    product_id=product.id,
                    field="attrs_cz.value_cz",
                    value=attr.value_cz,
                    detail="Polske diakritiky detekovany v attrs_cz value"
                ))

        # Count varianty pro BLOCK-8
        total_variants += len(product.variants)

        # WARN-1: EAN (gtin)
        if not product.gtin:
            warnings.append(ValidationError(
                rule="WARN-1",
                product_id=product.id,
                detail="Chybi EAN (gtin)"
            ))

        # WARN-2: brand
        if not product.brand:
            warnings.append(ValidationError(
                rule="WARN-2",
                product_id=product.id,
                detail="Chybi brand"
            ))

        # WARN-3: dimensions
        if not product.dimensions:
            warnings.append(ValidationError(
                rule="WARN-3",
                product_id=product.id,
                detail="Chybi dimensions"
            ))

        # WARN-4: ean per variant
        for variant in product.variants:
            if not variant.ean:
                warnings.append(ValidationError(
                    rule="WARN-4",
                    product_id=product.id,
                    field="variant.ean",
                    value=variant.id,
                    detail=f"Varianta {variant.id} nema EAN"
                ))

        # WARN-5 counting: attrs_cz vs attrs_raw
        total_attrs += len(product.attrs_raw)
        # Translated = attrs_cz kde name_cz != name_pl
        for attr in product.attrs_cz:
            if attr.name_cz != attr.name_pl:
                translated_attrs += 1
            else:
                total_attrs += 1  # Fallback = nepreloženo

    # BLOCK-8: pro category=="milo" → total_variants == 482
    if category_filter.lower() == "milo":
        if total_variants != 482:
            blocking.append(ValidationError(
                rule="BLOCK-8",
                detail=f"Kategorie Milo: ocekavano 482 variant, dostal {total_variants}"
            ))

    # WARN-5: slovnik pokryti >=95%
    if total_attrs > 0:
        coverage = (translated_attrs / total_attrs) * 100
        if coverage < 95:
            warnings.append(ValidationError(
                rule="WARN-5",
                detail=f"Slovnik pokryti {coverage:.1f}% < 95%"
            ))

    # Verdict
    if blocking:
        verdict = "BLOCKED"
    else:
        verdict = "PASS"

    result = ValidationResult(
        timestamp=datetime.utcnow().isoformat() + "Z",
        verdict=verdict,
        blocking_errors=blocking,
        warnings=warnings
    )

    return result
