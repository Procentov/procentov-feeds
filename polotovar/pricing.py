"""PLN → CZK konverze s koeficientem a per-produktovymi overridy.

KRITICKE: Cenova konverze zije POUZE tady, zadne Mergado pravidlo.
Lekce z 30 854 Kc incidentu - koeficient se nesmi nasobit dvakrat.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from decimal import Decimal
from pathlib import Path
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
import csv


# Globalni koeficient PLN → CZK (aktualizovat pri zmene kurzu)
KOEFICIENT_PLN_NA_CZK = Decimal("11.115")


class OverrideRow(BaseModel):
    """Jeden radek z cenove_overridy.csv."""
    id_produktu: str = Field(..., min_length=1)
    koeficient_override: Decimal = Field(..., gt=0, description="Koeficient pro tento produkt (napr. 1.5 = +50%)")
    poznamka: str = ""
    platnost_do: Optional[date] = None  # None = platnost neomezena


class PriceCZKResult(BaseModel):
    """Vysledek konverze PLN → CZK."""
    value: Decimal
    currency: str = "CZK"
    koeficient_used: Decimal
    override_applied: bool


def load_overrides(csv_path: str | Path) -> dict[str, OverrideRow]:
    """Nacte cenove_overridy.csv do dict[product_id, OverrideRow].

    Args:
        csv_path: Cesta k cenove_overridy.csv

    Returns:
        dict mapujici id_produktu na OverrideRow

    Raises:
        ValueError: Pokud CSV ma nevalidni strukturu nebo hodnoty
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        # Prazdny CSV je OK (zadne overridy)
        return {}

    overrides = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Validace hlavicky
        expected_cols = {'id_produktu', 'koeficient_override', 'poznamka', 'platnost_do'}
        if not expected_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV hlavicka nevalidni. Ocekavano: {expected_cols}, dostal: {reader.fieldnames}")

        for i, row in enumerate(reader, start=2):  # radek 1 = hlavicka, data od 2
            # Skip prazdne radky
            if not row['id_produktu'].strip():
                continue

            try:
                # Parse platnost_do
                platnost_do = None
                if row['platnost_do'].strip():
                    platnost_do = datetime.strptime(row['platnost_do'].strip(), '%Y-%m-%d').date()

                override = OverrideRow(
                    id_produktu=row['id_produktu'].strip(),
                    koeficient_override=Decimal(row['koeficient_override'].strip()),
                    poznamka=row['poznamka'].strip(),
                    platnost_do=platnost_do
                )
                overrides[override.id_produktu] = override

            except Exception as e:
                raise ValueError(f"Chyba pri parsovani CSV radek {i}: {e}")

    return overrides


def convert_pln_to_czk(
    pln_value: Decimal,
    product_id: str,
    overrides: dict[str, OverrideRow]
) -> PriceCZKResult:
    """Konvertuje PLN na CZK s aplikaci globalniho koeficientu a pripadneho overridu.

    Args:
        pln_value: Cena v PLN
        product_id: ID produktu (pro lookup overridu)
        overrides: dict overridu z load_overrides()

    Returns:
        PriceCZKResult s konvertovanou cenou v CZK

    Logika:
        1. Base konverze: pln_value * KOEFICIENT_PLN_NA_CZK
        2. Pokud existuje override a je platny (platnost_do >= dnes nebo None):
           czk_value = base * koeficient_override
        3. Zaokrouhleni na 2 des. mista
    """
    # Base konverze
    base_czk = pln_value * KOEFICIENT_PLN_NA_CZK
    koeficient_used = KOEFICIENT_PLN_NA_CZK
    override_applied = False

    # Check override
    override = overrides.get(product_id)
    if override:
        # Validace platnosti
        is_valid = True
        if override.platnost_do:
            today = date.today()
            is_valid = override.platnost_do >= today

        if is_valid:
            # Aplikuj override
            final_czk = base_czk * override.koeficient_override
            koeficient_used = KOEFICIENT_PLN_NA_CZK * override.koeficient_override
            override_applied = True
        else:
            # Override vyprsela platnost
            final_czk = base_czk
    else:
        final_czk = base_czk

    # Zaokrouhleni na 2 des. mista
    final_czk = final_czk.quantize(Decimal('0.01'))

    return PriceCZKResult(
        value=final_czk,
        currency="CZK",
        koeficient_used=koeficient_used,
        override_applied=override_applied
    )
