# tests/test_vault_agent.py — Teste unitare pentru VaultAgent (fara apeluri API)
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vault_agent import VaultAgent, CANONICAL_MAP, SKIP_TYPES, TYPE_ICONS, SKIP_PHRASES


class TestCanonicalMap:
    """Teste pentru maparea campurilor canonice."""

    def test_romanian_keys_mapped(self):
        assert CANONICAL_MAP["nume"] == "LastName"
        assert CANONICAL_MAP["prenume"] == "FirstName"
        assert CANONICAL_MAP["cnp"] == "CNP"
        assert CANONICAL_MAP["strada"] == "Street"
        assert CANONICAL_MAP["oras"] == "City"

    def test_english_keys_mapped(self):
        assert CANONICAL_MAP["last_name"] == "LastName"
        assert CANONICAL_MAP["first_name"] == "FirstName"
        assert CANONICAL_MAP["date_of_birth"] == "DateOfBirth"
        assert CANONICAL_MAP["passport_number"] == "PassportNo"

    def test_vehicle_keys_mapped(self):
        assert CANONICAL_MAP["vin"] == "VIN"
        assert CANONICAL_MAP["car_make"] == "CarMake"
        assert CANONICAL_MAP["car_model"] == "CarModel"
        assert CANONICAL_MAP["production_year"] == "ProductionYear"

    def test_spouse_keys_mapped(self):
        assert CANONICAL_MAP["spouse1_first_name"] == "Spouse1FirstName"
        assert CANONICAL_MAP["spouse2_cnp"] == "Spouse2CNP"

    def test_map_has_no_empty_values(self):
        for key, val in CANONICAL_MAP.items():
            assert val, f"Cheia '{key}' are valoare goala"
            assert val[0].isupper(), f"Valoarea '{val}' nu e PascalCase"


class TestNormalize:
    """Teste pentru normalizarea datelor extrase."""

    def test_basic_normalization(self):
        raw = {"last_name": "POPESCU", "first_name": "Ion"}
        result = VaultAgent._normalize(raw)
        assert result["LastName"] == "POPESCU"
        assert result["FirstName"] == "Ion"

    def test_null_values_filtered(self):
        raw = {"last_name": "POPESCU", "first_name": None, "cnp": ""}
        result = VaultAgent._normalize(raw)
        assert "LastName" in result
        assert "FirstName" not in result
        assert "CNP" not in result

    def test_na_values_filtered(self):
        raw = {"last_name": "POPESCU", "first_name": "N/A", "cnp": "not provided"}
        result = VaultAgent._normalize(raw)
        assert "FirstName" not in result
        assert "CNP" not in result

    def test_unknown_keys_ignored(self):
        raw = {"last_name": "POPESCU", "unknown_field_xyz": "some_value"}
        result = VaultAgent._normalize(raw)
        assert "LastName" in result
        assert len(result) == 1

    def test_whitespace_stripped(self):
        raw = {"last_name": "  POPESCU  ", "first_name": " Ion "}
        result = VaultAgent._normalize(raw)
        assert result["LastName"] == "POPESCU"
        assert result["FirstName"] == "Ion"

    def test_key_normalization_with_hyphens(self):
        raw = {"date-of-birth": "01/01/1990"}
        result = VaultAgent._normalize(raw)
        assert result.get("DateOfBirth") == "01/01/1990"

    def test_key_normalization_with_spaces(self):
        raw = {"last name": "POPESCU"}
        result = VaultAgent._normalize(raw)
        assert result.get("LastName") == "POPESCU"


class TestSkipTypes:
    """Teste pentru tipurile de pagini ignorate."""

    def test_blank_is_skipped(self):
        assert "blank_or_irrelevant" in SKIP_TYPES
        assert "blank" in SKIP_TYPES
        assert "empty" in SKIP_TYPES

    def test_valid_types_not_skipped(self):
        assert "identity_card" not in SKIP_TYPES
        assert "passport" not in SKIP_TYPES
        assert "birth_certificate" not in SKIP_TYPES


class TestTypeIcons:
    """Teste pentru iconitele tipurilor de documente."""

    def test_all_document_types_have_icons(self):
        expected_types = ["identity_card", "passport", "birth_certificate",
                          "vehicle_doc", "utility_bill", "marriage_certificate", "general"]
        for t in expected_types:
            assert t in TYPE_ICONS, f"Tipul '{t}' nu are icoana"


class TestAutoFillForm:
    """Teste pentru functionalitatea de auto-completare."""

    def setup_method(self):
        # Nu avem nevoie de API key pentru auto_fill_form
        self.agent = VaultAgent.__new__(VaultAgent)

    def test_full_match(self):
        vault = {"LastName": "POPESCU", "FirstName": "Ion", "CNP": "123"}
        required = {"LastName": "Nume", "FirstName": "Prenume", "CNP": "CNP"}
        result = self.agent.auto_fill_form(vault, required)
        assert len(result["filled"]) == 3
        assert len(result["missing"]) == 0

    def test_partial_match(self):
        vault = {"LastName": "POPESCU"}
        required = {"LastName": "Nume", "FirstName": "Prenume", "CNP": "CNP"}
        result = self.agent.auto_fill_form(vault, required)
        assert len(result["filled"]) == 1
        assert len(result["missing"]) == 2
        assert "FirstName" in result["missing"]

    def test_no_match(self):
        vault = {"VIN": "ABC123"}
        required = {"LastName": "Nume", "FirstName": "Prenume"}
        result = self.agent.auto_fill_form(vault, required)
        assert len(result["filled"]) == 0
        assert len(result["missing"]) == 2

    def test_empty_vault(self):
        vault = {}
        required = {"LastName": "Nume"}
        result = self.agent.auto_fill_form(vault, required)
        assert len(result["filled"]) == 0
        assert len(result["missing"]) == 1

    def test_empty_required(self):
        vault = {"LastName": "POPESCU"}
        required = {}
        result = self.agent.auto_fill_form(vault, required)
        assert len(result["filled"]) == 0
        assert len(result["missing"]) == 0


class TestSkipPhrases:
    """Teste pentru frazele ignorate la extragere."""

    def test_common_skip_phrases(self):
        assert "null" in SKIP_PHRASES
        assert "none" in SKIP_PHRASES
        assert "n/a" in SKIP_PHRASES
        assert "" in SKIP_PHRASES
        assert "not provided" in SKIP_PHRASES
