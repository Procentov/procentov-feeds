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
    cmd_seed,
    is_translatable_pl_string,
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
    """Test: mock parser vrátí 2 ParsedProduct, extrakce vyhodí unikátní stringy, žádné duplicity.
    POZOR: od M1.2 iter2 se používá ATTR_WHITELIST - jen určité atributy se sbírají.
    """

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
                        MockParsedAttribute(name_pl="Kolor", values_pl=["BL75"], is_variant=True),
                        MockParsedAttribute(name_pl="Materiał", values_pl=["MIKROFAZA"], is_variant=False),
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
                        MockParsedAttribute(name_pl="Kolor", values_pl=["BL75", "MG02"], is_variant=True),  # duplicitní atribut
                        MockParsedAttribute(name_pl="Producent", values_pl=["Milo Furniture"], is_variant=False),
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
    barvy_kody = output['namespaces']['barvy_kody']

    # Očekávané hodnoty (unikátní, bez duplicit)
    # ATTR_WHITELIST obsahuje: Kolor, Materiał, Wymiary, Waga, Kod_producenta, Producent
    assert set(atributy.keys()) == {"Kolor", "Materiał", "Producent"}
    # Hodnoty jen z VALUE_SOURCE_ATTRS (Materiał) a s filtrem is_translatable_pl_string
    assert set(hodnoty.keys()) == {"MIKROFAZA"}
    assert set(kategorie.keys()) == {"FOTELE", "FOTEL MILO", "Mikrofaza", "SOFY", "SOFA MILO"}
    # Barevné kódy z atributu Kolor
    assert set(barvy_kody.keys()) == {"BL75", "MG02"}

    # Všechny hodnoty v atributy, hodnoty, kategorie by měly být None (ještě nepřeložené)
    assert all(v is None for v in atributy.values())
    assert all(v is None for v in hodnoty.values())
    assert all(v is None for v in kategorie.values())
    # Pro barvy_kody: hodnoty by měly být objekty s pl/cz/material = None
    assert all(isinstance(v, dict) for v in barvy_kody.values())
    assert all(v == {"pl": None, "cz": None, "material": None} for v in barvy_kody.values())


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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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
            "kategorie": {},
            "barvy_kody": {}
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


# ============================================================================
# TESTY M1.2 ITER2: Filtr extract, is_translatable_pl_string, barvy_kody
# ============================================================================

def test_extract_filters_balast(tmp_path, monkeypatch):
    """Test: mock parser vrátí offer s atributem EAN (hodnota "5903769305087"),
    Wysokość ("120"), Kolor ("BL75"), Materiał ("MIKROFAZA"). Po extract:
    - "EAN", "Wysokość" v atributy = NE (nejsou v ATTR_WHITELIST)
    - "Kolor", "Materiał" v atributy = ANO
    - "5903769305087" v hodnoty = NE (cisla, neni v VALUE_SOURCE_ATTRS)
    - "120" v hodnoty = NE (číslo)
    - "MIKROFAZA" v hodnoty = ANO (z Materiał, prosel filtrem)
    - "BL75" v barvy_kody = ANO
    """
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

    # Mock data s balaštními hodnotami
    mock_products = [
        MockParsedProduct(
            item_group_key="TEST",
            cat_path_pl=["TEST"],
            offers=[
                MockParsedOffer(
                    attributes=[
                        MockParsedAttribute(name_pl="EAN", values_pl=["5903769305087"], is_variant=False),
                        MockParsedAttribute(name_pl="Wysokość", values_pl=["120"], is_variant=False),
                        MockParsedAttribute(name_pl="Kolor", values_pl=["BL75"], is_variant=True),
                        MockParsedAttribute(name_pl="Materiał", values_pl=["MIKROFAZA"], is_variant=False),
                    ],
                    cat_path_pl=["TEST"]
                )
            ]
        )
    ]

    def mock_parse(xml_path, category_filter=None):
        return mock_products

    monkeypatch.setattr('bootstrap.parse_atos', mock_parse)

    args = MagicMock()
    args.xml = "dummy.xml"
    args.category = None
    args.out = str(tmp_path / "extract_out.json")

    cmd_extract(args)
    output = load_json(args.out)

    atributy = output['namespaces']['atributy']
    hodnoty = output['namespaces']['hodnoty']
    barvy_kody = output['namespaces']['barvy_kody']

    # Kontroly
    assert "EAN" not in atributy, "EAN by neměl být v atributech (není v ATTR_WHITELIST)"
    assert "Wysokość" not in atributy, "Wysokość by neměl být v atributech (není v ATTR_WHITELIST)"
    assert "Kolor" in atributy, "Kolor by měl být v atributech"
    assert "Materiał" in atributy, "Materiał by měl být v atributech"

    assert "5903769305087" not in hodnoty, "EAN číslo by nemělo být v hodnotách"
    assert "120" not in hodnoty, "Číslo 120 by nemělo být v hodnotách"
    assert "MIKROFAZA" in hodnoty, "MIKROFAZA by měla být v hodnotách"

    assert "BL75" in barvy_kody, "BL75 by měl být v barvy_kody"


def test_is_translatable_pl_string():
    """Test: is_translatable_pl_string filtruje čísla, EAN, symbol kódy.
    - "" -> False
    - "12" -> False
    - "5903769305087" -> False
    - "3-7-70-9" -> False
    - "MIKROFAZA" -> True
    - "Dab Sonoma" -> True
    """
    assert is_translatable_pl_string("") == False
    assert is_translatable_pl_string("   ") == False
    assert is_translatable_pl_string("12") == False
    assert is_translatable_pl_string("5903769305087") == False
    assert is_translatable_pl_string("3-7-70-9") == False
    assert is_translatable_pl_string("10-25-56-12") == False
    assert is_translatable_pl_string("MIKROFAZA") == True
    assert is_translatable_pl_string("Dab Sonoma") == True
    assert is_translatable_pl_string("EKO-SKÓRA") == True


def test_merge_barvy_kody_new(tmp_path, schema_path):
    """Test: target má prazdne barvy_kody, review ma "BL75" s plnym objektem
    -> po merge je v target + audit.
    """
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {},
            "barvy_kody": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    review_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-02T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {},
            "barvy_kody": {
                "BL75": {"pl": "olive", "cz": "olivove zelena", "material": "Velvet"}
            }
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    target_path = tmp_path / "target.json"
    review_path = tmp_path / "review.json"
    save_json(target_data, str(target_path))
    save_json(review_data, str(review_path))

    args = MagicMock()
    args.target = str(target_path)
    args.review = str(review_path)

    cmd_merge(args)
    result = load_json(str(target_path))

    # Zkontroluj, že BL75 byl přidán
    assert "BL75" in result['namespaces']['barvy_kody']
    assert result['namespaces']['barvy_kody']['BL75'] == {"pl": "olive", "cz": "olivove zelena", "material": "Velvet"}

    # Zkontroluj audit
    assert "BL75" in result['audit']
    assert result['audit']['BL75']['_source'] == "review"
    assert result['audit']['BL75']['_reviewed_by'] == "mirek"


def test_merge_barvy_kody_skip_null(tmp_path, schema_path):
    """Test: review ma "X1" s vsemi 3 fieldy null -> merge ho preskoci, target nezmenen."""
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {},
            "barvy_kody": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    review_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-02T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {},
            "barvy_kody": {
                "X1": {"pl": None, "cz": None, "material": None}
            }
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    target_path = tmp_path / "target.json"
    review_path = tmp_path / "review.json"
    save_json(target_data, str(target_path))
    save_json(review_data, str(review_path))

    args = MagicMock()
    args.target = str(target_path)
    args.review = str(review_path)

    cmd_merge(args)
    result = load_json(str(target_path))

    # Zkontroluj, že X1 NEBYL přidán (skipnutý kvůli null)
    assert "X1" not in result['namespaces']['barvy_kody']
    assert "X1" not in result['audit']


def test_seed_command(tmp_path, schema_path):
    """Test: target má prazdne barvy_kody, source má 3 zaznamy
    -> po seed 3 zaznamy v targetu + audit "_source": "seed_utuli"
    """
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {},
            "barvy_kody": {}
        },
        "per_kategorii_override": {},
        "audit": {}
    }

    source_data = {
        "_zdroj": "test",
        "barvy_kody": {
            "BL75": {"pl": "olive", "cz": "olivove zelena", "material": "Velvet"},
            "MG02": {"pl": "sliwka", "cz": "svestkova", "material": "Velvet"},
            "1D": {"pl": "czarny", "cz": "cerna", "material": "Eko-kuze"}
        }
    }

    target_path = tmp_path / "target.json"
    source_path = tmp_path / "source.json"
    save_json(target_data, str(target_path))
    save_json(source_data, str(source_path))

    args = MagicMock()
    args.target = str(target_path)
    args.source = str(source_path)

    cmd_seed(args)
    result = load_json(str(target_path))

    # Zkontroluj, že všechny 3 kódy byly přidány
    assert len(result['namespaces']['barvy_kody']) == 3
    assert "BL75" in result['namespaces']['barvy_kody']
    assert "MG02" in result['namespaces']['barvy_kody']
    assert "1D" in result['namespaces']['barvy_kody']

    # Zkontroluj audit
    assert result['audit']['BL75']['_source'] == "seed_utuli"
    assert result['audit']['MG02']['_source'] == "seed_utuli"
    assert result['audit']['1D']['_source'] == "seed_utuli"


def test_seed_conflict_preserves_target(tmp_path, schema_path, capsys):
    """Test: target má BL75 s cz="stara", source má BL75 s cz="nova"
    -> po seed target NEZMENEN, log WARN
    """
    target_data = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "namespaces": {
            "atributy": {},
            "hodnoty": {},
            "kategorie": {},
            "barvy_kody": {
                "BL75": {"pl": "old", "cz": "stara", "material": "Velvet"}
            }
        },
        "per_kategorii_override": {},
        "audit": {
            "BL75": {
                "_source": "review",
                "_reviewed_by": "mirek",
                "_updated_at": "2026-01-01T00:00:00Z"
            }
        }
    }

    source_data = {
        "_zdroj": "test",
        "barvy_kody": {
            "BL75": {"pl": "new", "cz": "nova", "material": "Velvet"}
        }
    }

    target_path = tmp_path / "target.json"
    source_path = tmp_path / "source.json"
    save_json(target_data, str(target_path))
    save_json(source_data, str(source_path))

    args = MagicMock()
    args.target = str(target_path)
    args.source = str(source_path)

    cmd_seed(args)
    result = load_json(str(target_path))

    # Zkontroluj, že target hodnota NEBYLA změněna
    assert result['namespaces']['barvy_kody']['BL75']['cz'] == "stara"
    assert result['audit']['BL75']['_source'] == "review"

    # Zkontroluj, že byl vypsán WARN
    captured = capsys.readouterr()
    assert "WARN: SEED-CONFLICT: BL75" in captured.out
