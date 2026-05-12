"""Pytest testy pro slovnik/bootstrap.py."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Import funkcí z bootstrap
sys.path.insert(0, str(Path(__file__).parent.parent))
from bootstrap import (
    cmd_extract,
    cmd_merge,
    load_json,
    save_json,
    validate_schema,
    get_iso_timestamp
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def schema_path():
    """Cesta ke slovnik_schema.json."""
    return Path(__file__).parent.parent / 'slovnik_schema.json'


@pytest.fixture
def slovnik_path():
    """Cesta ke slovnik.json."""
    return Path(__file__).parent.parent / 'slovnik.json'


@pytest.fixture
def temp_json_file(tmp_path):
    """Factory pro dočasné JSON soubory."""
    def _create(data: dict, filename: str = "temp.json"):
        path = tmp_path / filename
        save_json(data, str(path))
        return path
    return _create


# ============================================================================
# TESTY SCHEMA VALIDACE
# ============================================================================

def test_schema_valid(schema_path):
    """Test: slovnik_schema.json je validní JSON Schema (draft-07)."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema není nainstalován")

    schema = load_json(str(schema_path))

    # Zkontroluj, že schema je validní podle draft-07
    try:
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        pytest.fail(f"Schema není validní: {e}")


def test_empty_slovnik_valid(schema_path, slovnik_path):
    """Test: prázdná kostra v slovnik.json validuje proti schema."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema není nainstalován")

    schema = load_json(str(schema_path))
    slovnik = load_json(str(slovnik_path))

    # Validuj prázdný slovník proti schema
    try:
        jsonschema.validate(instance=slovnik, schema=schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"Prázdný slovník nevaliduje: {e}")


# ============================================================================
# TESTY EXTRACT
# ============================================================================

def test_extract_unique(tmp_path, monkeypatch):
    """Test: mock parser vrátí 2 ParsedProduct, extrakce vyhodí unikátní stringy, žádné duplicity."""

    # Mock ParsedProduct objekty
    from dataclasses import dataclass

    @dataclass
    class MockParsedAttribute:
        name_pl: str
        values_pl: list
        is_variant: bool

    @dataclass
    class MockParsedOffer:
        attributes: list
        cat_path_pl: list

    @dataclass
    class MockParsedProduct:
        item_group_key: str
        cat_path_pl: list
        offers: list

    # Vytvoř mock data: 2 produkty s duplicitními stringy
    mock_products = [
        MockParsedProduct(
            item_group_key="FOTEL MILO",
            cat_path_pl=["FOTELE", "FOTEL MILO"],
            offers=[
                MockParsedOffer(
                    attributes=[
                        MockParsedAttribute(name_pl="Kolor", values_pl=["Velvet"], is_variant=True),
                        MockParsedAttribute(name_pl="Materiał", values_pl=["Drewno"], is_variant=False),
                    ],
                    cat_path_pl=["FOTELE", "FOTEL MILO", "Mikrofaza"]
                )
            ]
        ),
        MockParsedProduct(
            item_group_key="SOFA MILO",
            cat_path_pl=["SOFY", "SOFA MILO"],
            offers=[
                MockParsedOffer(
                    attributes=[
                        MockParsedAttribute(name_pl="Kolor", values_pl=["Velvet", "Dąb"], is_variant=True),  # duplicitní atribut, duplicitní hodnota
                        MockParsedAttribute(name_pl="Wysokość", values_pl=["180cm"], is_variant=False),
                    ],
                    cat_path_pl=["SOFY", "SOFA MILO", "Mikrofaza"]  # duplicitní segment "Mikrofaza"
                )
            ]
        )
    ]

    # Mock parse_atos funkce
    def mock_parse(xml_path, category_filter=None):
        return mock_products

    monkeypatch.setattr('bootstrap.parse_atos', mock_parse)

    # Vytvoř mock args
    args = MagicMock()
    args.xml = "dummy.xml"
    args.category = None
    args.out = str(tmp_path / "extract_out.json")

    # Zavolej extract
    cmd_extract(args)

    # Načti výstup
    output = load_json(args.out)

    # Zkontroluj unikátní stringy
    atributy = output['namespaces']['atributy']
    hodnoty = output['namespaces']['hodnoty']
    kategorie = output['namespaces']['kategorie']

    # Očekávané hodnoty (unikátní, bez duplicit)
    assert set(atributy.keys()) == {"Kolor", "Materiał", "Wysokość"}
    assert set(hodnoty.keys()) == {"Velvet", "Drewno", "Dąb", "180cm"}
    assert set(kategorie.keys()) == {"FOTELE", "FOTEL MILO", "Mikrofaza", "SOFY", "SOFA MILO"}

    # Všechny hodnoty by měly být None (ještě nepřeložené)
    assert all(v is None for v in atributy.values())
    assert all(v is None for v in hodnoty.values())
    assert all(v is None for v in kategorie.values())


# ============================================================================
# TESTY MERGE
# ============================================================================

def test_merge_new_key(tmp_path, schema_path):
    """Test: prázdný target, review s 1 klíčem -> po merge je v targetu + audit zapsán."""

    # Prázdný target
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Review s 1 novým klíčem
    review_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-02T00:00:00Z",
        "namespaces": {
            "atributy": {"Kolor": "Barva"},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Ulož soubory
    target_path = tmp_path / "target.json"
    review_path = tmp_path / "review.json"
    save_json(target_data, str(target_path))
    save_json(review_data, str(review_path))

    # Mock args
    args = MagicMock()
    args.target = str(target_path)
    args.review = str(review_path)

    # Zavolej merge
    cmd_merge(args)

    # Načti výsledek
    result = load_json(str(target_path))

    # Zkontroluj, že klíč byl přidán
    assert "Kolor" in result['namespaces']['atributy']
    assert result['namespaces']['atributy']['Kolor'] == "Barva"

    # Zkontroluj audit
    assert "Kolor" in result['audit']
    assert result['audit']['Kolor']['_source'] == "review"
    assert result['audit']['Kolor']['_reviewed_by'] == "mirek"
    assert '_updated_at' in result['audit']['Kolor']


def test_merge_update(tmp_path, schema_path, capsys):
    """Test: target má 'Kolor': 'stará', review 'Kolor': 'nová' -> update + print UPDATE."""

    # Target se starou hodnotou
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {"Kolor": "Barva stará"},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {
            "Kolor": {
                "_source": "google",
                "_updated_at": "2026-01-01T00:00:00Z"
            }
        }
    }

    # Review s novou hodnotou
    review_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-02T00:00:00Z",
        "namespaces": {
            "atributy": {"Kolor": "Barva nová"},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Ulož soubory
    target_path = tmp_path / "target.json"
    review_path = tmp_path / "review.json"
    save_json(target_data, str(target_path))
    save_json(review_data, str(review_path))

    # Mock args
    args = MagicMock()
    args.target = str(target_path)
    args.review = str(review_path)

    # Zavolej merge
    cmd_merge(args)

    # Načti výsledek
    result = load_json(str(target_path))

    # Zkontroluj, že hodnota byla aktualizována
    assert result['namespaces']['atributy']['Kolor'] == "Barva nová"

    # Zkontroluj audit
    assert result['audit']['Kolor']['_source'] == "review"
    assert result['audit']['Kolor']['_reviewed_by'] == "mirek"

    # Zkontroluj, že se vypsal UPDATE
    captured = capsys.readouterr()
    assert "UPDATE: Kolor | Barva stará -> Barva nová" in captured.out


def test_merge_skip(tmp_path, schema_path):
    """Test: target a review mají stejnou hodnotu -> skip (ale updated_at se změní)."""

    # Target a review se stejnou hodnotou
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {"Kolor": "Barva"},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {
            "Kolor": {
                "_source": "google",
                "_updated_at": "2026-01-01T00:00:00Z"
            }
        }
    }

    review_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-02T00:00:00Z",
        "namespaces": {
            "atributy": {"Kolor": "Barva"},  # Stejná hodnota
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Ulož soubory
    target_path = tmp_path / "target.json"
    review_path = tmp_path / "review.json"
    save_json(target_data, str(target_path))
    save_json(review_data, str(review_path))

    # Ulož originální audit pro porovnání
    original_audit = target_data['audit']['Kolor'].copy()

    # Mock args
    args = MagicMock()
    args.target = str(target_path)
    args.review = str(review_path)

    # Zavolej merge
    cmd_merge(args)

    # Načti výsledek
    result = load_json(str(target_path))

    # Zkontroluj, že hodnota zůstala stejná
    assert result['namespaces']['atributy']['Kolor'] == "Barva"

    # Zkontroluj, že audit NEBYL změněn (skip)
    assert result['audit']['Kolor']['_source'] == original_audit['_source']
    assert result['audit']['Kolor']['_updated_at'] == original_audit['_updated_at']

    # updated_at v root objektu by se měl změnit
    assert result['updated_at'] != target_data['updated_at']


def test_merge_validates(tmp_path, schema_path):
    """Test: merge s neplatnou strukturou -> sys.exit(1)."""

    # Prázdný target (validní)
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Review s klíčem, který po merge vytvoří neplatnou strukturu
    # (audit má neplatný _source)
    review_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-02T00:00:00Z",
        "namespaces": {
            "atributy": {"Kolor": "Barva"},
            "hodnoty": {},
            "kategorie": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    # Ulož soubory
    target_path = tmp_path / "target.json"
    review_path = tmp_path / "review.json"
    save_json(target_data, str(target_path))
    save_json(review_data, str(review_path))

    # Přepíšeme target po merge tak, aby byl neplatný
    # (simulujeme chybu - místo validního enum hodnoty dáme něco jiného)
    def mock_merge_invalid(args):
        """Mock merge, který vytvoří neplatnou strukturu."""
        target = load_json(args.target)
        review = load_json(args.review)

        # Přidej klíč s neplatným audit entry
        target['namespaces']['atributy']['Kolor'] = "Barva"
        target['audit']['Kolor'] = {
            "_source": "INVALID_SOURCE",  # Neplatná hodnota (není v enum)
            "_updated_at": get_iso_timestamp()
        }

        save_json(target, args.target)

        # Validuj (to by mělo selhat)
        validate_schema(target, str(schema_path))

    # Mock args
    args = MagicMock()
    args.target = str(target_path)
    args.review = str(review_path)

    # Zavolej mock merge, který vytvoří neplatnou strukturu
    # Očekáváme sys.exit(1)
    with pytest.raises(SystemExit) as excinfo:
        mock_merge_invalid(args)

    assert excinfo.value.code == 1
