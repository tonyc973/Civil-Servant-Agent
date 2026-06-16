# tests/test_mcp_server.py — Teste unitare pentru instrumentele MCP
import pytest
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.mcp_server import (
    verify_cnp, check_vehicle_status,
    get_available_appointments, estimate_processing_time,
    check_required_documents,
)


class TestVerifyCNP:
    """Teste pentru validarea CNP-ului."""

    def test_valid_cnp_from_registry(self):
        result = json.loads(verify_cnp("1900101123457"))
        assert result["valid"] is True
        assert result["data"]["name"] == "Ion Popescu"

    def test_invalid_cnp_too_short(self):
        result = json.loads(verify_cnp("12345"))
        assert result["valid"] is False
        assert "13 cifre" in result["error"]

    def test_invalid_cnp_not_digits(self):
        result = json.loads(verify_cnp("abcdefghijklm"))
        assert result["valid"] is False

    def test_invalid_cnp_wrong_checksum(self):
        result = json.loads(verify_cnp("1900101123450"))
        assert result["valid"] is False
        assert "control" in result["error"].lower() or "checksum" in result["error"].lower()

    def test_valid_cnp_not_in_registry(self):
        # CNP valid matematic dar necunoscut in registru
        # 2850101018188 — checksum valid
        result = json.loads(verify_cnp("2850101018186"))
        assert result["valid"] is True
        assert result["data"]["name"] == "Cetățean Necunoscut"

    def test_cnp_with_whitespace_trimmed(self):
        result = json.loads(verify_cnp("  1900101123457  "))
        assert result["valid"] is True

    def test_invalid_month_in_cnp(self):
        result = json.loads(verify_cnp("1901301123455"))
        assert result["valid"] is False
        assert "luna" in result["error"].lower() or "month" in result["error"].lower()

    def test_female_cnp_detected(self):
        result = json.loads(verify_cnp("2950505987655"))
        assert result["valid"] is True
        assert result["data"]["name"] == "Maria Ionescu"


class TestCheckVehicleStatus:
    """Teste pentru verificarea VIN-ului."""

    def test_known_vehicle_found(self):
        result = json.loads(check_vehicle_status("WBAWB73569P019296"))
        assert result["found"] is True
        assert result["data"]["make"] == "BMW"

    def test_stolen_vehicle_flagged(self):
        result = json.loads(check_vehicle_status("VF1RFD00X56789012"))
        assert result["found"] is True
        assert result["data"]["status"] == "Furat"

    def test_unknown_vin(self):
        result = json.loads(check_vehicle_status("UNKNOWN123456789"))
        assert result["found"] is False

    def test_vin_case_insensitive(self):
        result = json.loads(check_vehicle_status("wbawb73569p019296"))
        assert result["found"] is True


class TestGetAvailableAppointments:
    """Teste pentru programari."""

    def test_returns_slots(self):
        result = json.loads(get_available_appointments("identity_card"))
        assert "available_slots" in result
        assert len(result["available_slots"]) > 0

    def test_note_in_romanian(self):
        result = json.loads(get_available_appointments("identity_card"))
        assert "ordinea" in result["note"].lower() or "programar" in result["note"].lower()

    def test_slot_has_date_time_office(self):
        result = json.loads(get_available_appointments("identity_card"))
        slot = result["available_slots"][0]
        assert "date" in slot
        assert "time" in slot
        assert "office" in slot


class TestEstimateProcessingTime:
    """Teste pentru estimarile de timp."""

    def test_standard_mode(self):
        result = json.loads(estimate_processing_time("identity_card", False))
        assert result["mode"] == "standard"
        assert "zile" in result["estimated_time"].lower()

    def test_urgent_mode(self):
        result = json.loads(estimate_processing_time("identity_card", True))
        assert result["mode"] == "urgent"
        assert "ore" in result["estimated_time"].lower()

    def test_fee_note_present(self):
        result = json.loads(estimate_processing_time("identity_card", True))
        assert "taxa" in result["fee_note"].lower() or "taxă" in result["fee_note"].lower()


class TestCheckRequiredDocuments:
    """Teste pentru lista de documente necesare."""

    def test_identity_card_documents(self):
        result = json.loads(check_required_documents("identity_card"))
        assert "required_documents" in result
        assert len(result["required_documents"]) == 5

    def test_documents_in_romanian(self):
        result = json.loads(check_required_documents("identity_card"))
        docs = result["required_documents"]
        assert any("naștere" in d.lower() or "nastere" in d.lower() for d in docs)

    def test_unknown_service_returns_fallback(self):
        result = json.loads(check_required_documents("nonexistent"))
        docs = result["required_documents"]
        assert len(docs) == 1
        assert "contacta" in docs[0].lower() or "biroul" in docs[0].lower()
