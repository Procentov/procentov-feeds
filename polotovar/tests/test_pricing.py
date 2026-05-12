"""Testy pro pricing.py - PLN→CZK konverze."""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path
import tempfile
import csv

from polotovar.pricing import (
    KOEFICIENT_PLN_NA_CZK,
    OverrideRow,
    load_overrides,
    convert_pln_to_czk
)


def test_koeficient_constant():
    """Test: globalni koeficient je spravne nastaven."""
    assert KOEFICIENT_PLN_NA_CZK == Decimal("11.115")


def test_convert_pln_to_czk_bez_override():
    """Test: base konverze PLN→CZK bez override."""
    pln = Decimal("100.00")
    result = convert_pln_to_czk(pln, "produkt_123", {})

    expected_czk = Decimal("100.00") * Decimal("11.115")
    assert result.value == expected_czk.quantize(Decimal('0.01'))
    assert result.currency == "CZK"
    assert result.koeficient_used == KOEFICIENT_PLN_NA_CZK
    assert result.override_applied is False


def test_convert_pln_to_czk_s_override_platnym():
    """Test: konverze s platnym override."""
    pln = Decimal("100.00")
    overrides = {
        "produkt_123": OverrideRow(
            id_produktu="produkt_123",
            koeficient_override=Decimal("1.5"),
            poznamka="Test",
            platnost_do=date.today() + timedelta(days=30)
        )
    }

    result = convert_pln_to_czk(pln, "produkt_123", overrides)

    # Base: 100 * 11.115 = 1111.5
    # Override: 1111.5 * 1.5 = 1667.25
    expected_czk = Decimal("1667.25")
    assert result.value == expected_czk
    assert result.override_applied is True
    assert result.koeficient_used == KOEFICIENT_PLN_NA_CZK * Decimal("1.5")


def test_convert_pln_to_czk_s_override_neplatnym():
    """Test: konverze s override jehož platnost_do vyprsela."""
    pln = Decimal("100.00")
    overrides = {
        "produkt_123": OverrideRow(
            id_produktu="produkt_123",
            koeficient_override=Decimal("2.0"),
            poznamka="Expired",
            platnost_do=date.today() - timedelta(days=1)  # vcera
        )
    }

    result = convert_pln_to_czk(pln, "produkt_123", overrides)

    # Override vyprsela platnost, pouzije se base koeficient
    expected_czk = (Decimal("100.00") * KOEFICIENT_PLN_NA_CZK).quantize(Decimal('0.01'))
    assert result.value == expected_czk
    assert result.override_applied is False


def test_convert_pln_to_czk_s_override_neomezena_platnost():
    """Test: override s platnost_do=None (neomezena platnost)."""
    pln = Decimal("100.00")
    overrides = {
        "produkt_123": OverrideRow(
            id_produktu="produkt_123",
            koeficient_override=Decimal("1.2"),
            poznamka="Permanent",
            platnost_do=None
        )
    }

    result = convert_pln_to_czk(pln, "produkt_123", overrides)

    expected_czk = (Decimal("100.00") * KOEFICIENT_PLN_NA_CZK * Decimal("1.2")).quantize(Decimal('0.01'))
    assert result.value == expected_czk
    assert result.override_applied is True


def test_load_overrides_prazdny_csv():
    """Test: load_overrides z prazdneho CSV."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id_produktu', 'koeficient_override', 'poznamka', 'platnost_do'])
        csv_path = f.name

    try:
        overrides = load_overrides(csv_path)
        assert len(overrides) == 0
    finally:
        Path(csv_path).unlink()


def test_load_overrides_s_daty():
    """Test: load_overrides z CSV s daty."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id_produktu', 'koeficient_override', 'poznamka', 'platnost_do'])
        writer.writerow(['prod_1', '1.5', 'Test override', '2026-12-31'])
        writer.writerow(['prod_2', '2.0', 'Another test', ''])  # prazdna platnost_do
        csv_path = f.name

    try:
        overrides = load_overrides(csv_path)
        assert len(overrides) == 2
        assert 'prod_1' in overrides
        assert overrides['prod_1'].koeficient_override == Decimal('1.5')
        assert overrides['prod_1'].platnost_do == date(2026, 12, 31)
        assert 'prod_2' in overrides
        assert overrides['prod_2'].platnost_do is None
    finally:
        Path(csv_path).unlink()


def test_load_overrides_neexistujici_soubor():
    """Test: load_overrides z neexistujiciho souboru vraci prazdny dict."""
    overrides = load_overrides("/neexistujici/cesta.csv")
    assert len(overrides) == 0
