"""Testy pro translator.py - PL→CZ preklady."""

import pytest
import json
import tempfile
from pathlib import Path

from polotovar.translator import (
    load_slovnik,
    translate_attribute_name,
    translate_attribute_value,
    translate_category_segment,
    decode_color_code
)


@pytest.fixture
def mock_slovnik():
    """Fixture: minimalni slovnik pro testy."""
    slovnik = {
        "schema_version": "1.0",
        "updated_at": "2026-05-12T00:00:00Z",
        "namespaces": {
            "atributy": {
                "Kolor": "Barva",
                "Materiał": "Materiál",
                "Waga": "Hmotnost"
            },
            "hodnoty": {
                "VELVET": "Samet",
                "MIKROFAZA": "Mikrovlákno"
            },
            "kategorie": {
                "FOTELE": "Křesla",
                "FOTEL MILO": "Křeslo Milo"
            },
            "barvy_kody": {
                "MG02": {"pl": "sliwka", "cz": "svestkova", "material": "Velvet"},
                "1D": {"pl": "czarny", "cz": "cerna", "material": "Eko-kuze"}
            }
        },
        "per_kategorii_override": {
            "FOTELE": {
                "Waga": "Hmotnost křesla"
            }
        },
        "audit": {}
    }
    return slovnik


@pytest.fixture
def mock_slovnik_file(mock_slovnik):
    """Fixture: slovnik jako docasny JSON soubor."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(mock_slovnik, f, ensure_ascii=False, indent=2)
        slovnik_path = f.name

    yield slovnik_path

    # Cleanup
    Path(slovnik_path).unlink()


def test_load_slovnik(mock_slovnik_file):
    """Test: load_slovnik nacte JSON."""
    slovnik = load_slovnik(mock_slovnik_file)
    assert 'namespaces' in slovnik
    assert 'atributy' in slovnik['namespaces']


def test_load_slovnik_neexistujici_soubor():
    """Test: load_slovnik hodi ValueError pokud soubor neexistuje."""
    with pytest.raises(ValueError, match="Slovnik neexistuje"):
        load_slovnik("/neexistujici/slovnik.json")


def test_translate_attribute_name(mock_slovnik):
    """Test: translate_attribute_name prelozi nazev atributu."""
    assert translate_attribute_name("Kolor", mock_slovnik) == "Barva"
    assert translate_attribute_name("Materiał", mock_slovnik) == "Materiál"


def test_translate_attribute_name_fallback(mock_slovnik, capsys):
    """Test: translate_attribute_name vraci PL fallback pokud neni v slovniku."""
    result = translate_attribute_name("Neznamy", mock_slovnik)
    assert result == "Neznamy"

    # Check warning v stdout
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "Neznamy" in captured.out


def test_translate_attribute_name_per_kategorie_override(mock_slovnik):
    """Test: per-kategorii override ma prioritu."""
    result = translate_attribute_name("Waga", mock_slovnik, kategorie_context="FOTELE")
    assert result == "Hmotnost křesla"

    # Bez kontextu pouzije globalni
    result = translate_attribute_name("Waga", mock_slovnik)
    assert result == "Hmotnost"


def test_translate_attribute_value(mock_slovnik):
    """Test: translate_attribute_value prelozi hodnotu."""
    assert translate_attribute_value("VELVET", mock_slovnik) == "Samet"
    assert translate_attribute_value("MIKROFAZA", mock_slovnik) == "Mikrovlákno"


def test_translate_attribute_value_fallback(mock_slovnik, capsys):
    """Test: translate_attribute_value vraci PL fallback."""
    result = translate_attribute_value("Neznama Hodnota", mock_slovnik)
    assert result == "Neznama Hodnota"

    captured = capsys.readouterr()
    assert "WARNING" in captured.out


def test_translate_category_segment(mock_slovnik):
    """Test: translate_category_segment prelozi segment kategorie."""
    assert translate_category_segment("FOTELE", mock_slovnik) == "Křesla"
    assert translate_category_segment("FOTEL MILO", mock_slovnik) == "Křeslo Milo"


def test_translate_category_segment_fallback(mock_slovnik, capsys):
    """Test: translate_category_segment fallback."""
    result = translate_category_segment("NEZNAMA KATEGORIE", mock_slovnik)
    assert result == "NEZNAMA KATEGORIE"

    captured = capsys.readouterr()
    assert "WARNING" in captured.out


def test_decode_color_code(mock_slovnik):
    """Test: decode_color_code dekoduje barevny kod."""
    cz_barva, material = decode_color_code("MG02", mock_slovnik)
    assert cz_barva == "svestkova"
    assert material == "Velvet"

    cz_barva, material = decode_color_code("1D", mock_slovnik)
    assert cz_barva == "cerna"
    assert material == "Eko-kuze"


def test_decode_color_code_neznamy_kod(mock_slovnik, capsys):
    """Test: decode_color_code fallback pro neznamy kod."""
    cz_barva, material = decode_color_code("UNKNOWN_CODE", mock_slovnik)
    assert cz_barva == "UNKNOWN_CODE"
    assert material is None

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
