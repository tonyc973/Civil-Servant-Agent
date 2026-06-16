# tests/test_database.py — Teste unitare pentru modulul de baza de date
import pytest
import os
import sys
import sqlite3
import json

# Adaugam directorul radacina la path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import (
    get_connection, init_db, seed_db,
    get_all_services, get_service, get_citizen, get_vehicle,
    get_appointments, get_required_documents, get_processing_time,
    save_vault_field, save_vault_fields, get_vault_fields, clear_vault,
    save_vault_document, get_vault_documents, delete_vault_documents_by_folder,
    is_folder_scanned, is_file_in_vault, DB_PATH,
)


class TestDatabaseConnection:
    """Teste pentru conexiunea la baza de date."""

    def test_connection_returns_sqlite_connection(self):
        conn = get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_connection_has_row_factory(self):
        conn = get_connection()
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_database_file_exists(self):
        assert os.path.exists(DB_PATH), "Fisierul bazei de date nu exista"


class TestDatabaseSchema:
    """Teste pentru structura tabelelor."""

    def test_all_tables_exist(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "services", "service_fields", "citizens", "vehicles",
            "appointments", "required_documents", "processing_times",
            "vault_fields", "vault_documents"
        }
        for t in expected:
            assert t in tables, f"Tabela '{t}' lipseste din baza de date"

    def test_services_table_has_correct_columns(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(services)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "key" in columns
        assert "name" in columns
        assert "icon" in columns
        assert "description" in columns
        assert "template_file" in columns

    def test_vault_fields_table_has_correct_columns(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(vault_fields)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "field_key" in columns
        assert "field_value" in columns


class TestServices:
    """Teste pentru serviciile guvernamentale."""

    def test_get_all_services_returns_dict(self):
        services = get_all_services()
        assert isinstance(services, dict)

    def test_all_six_services_exist(self):
        services = get_all_services()
        expected_keys = [
            "identity_card", "passport_renewal", "vehicle_registration",
            "birth_certificate", "marriage_certificate", "fiscal_certificate"
        ]
        for key in expected_keys:
            assert key in services, f"Serviciul '{key}' lipseste"

    def test_service_has_required_structure(self):
        services = get_all_services()
        for key, svc in services.items():
            assert "name" in svc, f"'{key}' nu are 'name'"
            assert "icon" in svc, f"'{key}' nu are 'icon'"
            assert "description" in svc, f"'{key}' nu are 'description'"
            assert "template_file" in svc, f"'{key}' nu are 'template_file'"
            assert "required_fields" in svc, f"'{key}' nu are 'required_fields'"
            assert "estimated_time" in svc, f"'{key}' nu are 'estimated_time'"
            assert isinstance(svc["required_fields"], dict)

    def test_identity_card_has_8_fields(self):
        svc = get_service("identity_card")
        assert svc is not None
        assert len(svc["required_fields"]) == 8

    def test_service_fields_are_in_romanian(self):
        svc = get_service("identity_card")
        fields = svc["required_fields"]
        assert fields["LastName"] == "Nume de Familie"
        assert fields["FirstName"] == "Prenume"
        assert "CNP" in fields["CNP"]

    def test_get_nonexistent_service_returns_none(self):
        svc = get_service("nonexistent_service_xyz")
        assert svc is None

    def test_passport_renewal_has_6_fields(self):
        svc = get_service("passport_renewal")
        assert len(svc["required_fields"]) == 6

    def test_vehicle_registration_has_6_fields(self):
        svc = get_service("vehicle_registration")
        assert len(svc["required_fields"]) == 6


class TestCitizens:
    """Teste pentru registrul de cetateni."""

    def test_known_citizen_found(self):
        citizen = get_citizen("1900101123457")
        assert citizen is not None
        assert citizen["name"] == "Ion Popescu"

    def test_citizen_has_all_fields(self):
        citizen = get_citizen("1900101123457")
        assert "name" in citizen
        assert "dob" in citizen
        assert "status" in citizen
        assert "address" in citizen

    def test_unknown_citizen_returns_none(self):
        citizen = get_citizen("0000000000000")
        assert citizen is None

    def test_citizen_status_in_romanian(self):
        citizen = get_citizen("1900101123457")
        assert citizen["status"] == "Fără cazier"

    def test_all_three_citizens_exist(self):
        cnps = ["1900101123457", "2950505987655", "1850320556786"]
        for cnp in cnps:
            assert get_citizen(cnp) is not None, f"Cetateanul cu CNP {cnp} lipseste"


class TestVehicles:
    """Teste pentru registrul de vehicule."""

    def test_known_vehicle_found(self):
        vehicle = get_vehicle("WBAWB73569P019296")
        assert vehicle is not None
        assert vehicle["make"] == "BMW"
        assert vehicle["model"] == "320d"

    def test_stolen_vehicle_detected(self):
        vehicle = get_vehicle("VF1RFD00X56789012")
        assert vehicle is not None
        assert vehicle["status"] == "Furat"

    def test_unknown_vin_returns_none(self):
        vehicle = get_vehicle("UNKNOWN_VIN_12345")
        assert vehicle is None

    def test_vehicle_year_is_integer(self):
        vehicle = get_vehicle("WBAWB73569P019296")
        assert isinstance(vehicle["year"], int)
        assert vehicle["year"] == 2009


class TestAppointments:
    """Teste pentru programari."""

    def test_appointments_returns_list(self):
        slots = get_appointments()
        assert isinstance(slots, list)

    def test_appointments_not_empty(self):
        slots = get_appointments()
        assert len(slots) > 0

    def test_appointment_has_required_fields(self):
        slots = get_appointments(limit=1)
        slot = slots[0]
        assert "date" in slot
        assert "time" in slot
        assert "office" in slot

    def test_limit_parameter_works(self):
        slots_2 = get_appointments(limit=2)
        slots_5 = get_appointments(limit=5)
        assert len(slots_2) == 2
        assert len(slots_5) == 5

    def test_total_appointments_count(self):
        slots = get_appointments(limit=100)
        assert len(slots) == 8


class TestRequiredDocuments:
    """Teste pentru documentele necesare per serviciu."""

    def test_identity_card_has_5_documents(self):
        docs = get_required_documents("identity_card")
        assert len(docs) == 5

    def test_documents_are_in_romanian(self):
        docs = get_required_documents("identity_card")
        assert any("naștere" in d.lower() for d in docs)

    def test_unknown_service_returns_empty(self):
        docs = get_required_documents("nonexistent")
        assert docs == []

    def test_all_services_have_documents(self):
        for key in ["identity_card", "passport_renewal", "vehicle_registration",
                     "birth_certificate", "marriage_certificate", "fiscal_certificate"]:
            docs = get_required_documents(key)
            assert len(docs) > 0, f"Serviciul '{key}' nu are documente"


class TestProcessingTimes:
    """Teste pentru estimarile de timp."""

    def test_identity_card_processing_time(self):
        times = get_processing_time("identity_card")
        assert "standard" in times
        assert "urgent" in times
        assert "zile" in times["standard"].lower() or "ore" in times["standard"].lower()

    def test_unknown_service_returns_default(self):
        times = get_processing_time("nonexistent")
        assert times["standard"] == "Necunoscut"
        assert times["urgent"] == "Necunoscut"

    def test_all_services_have_times(self):
        for key in ["identity_card", "passport_renewal", "vehicle_registration",
                     "birth_certificate", "marriage_certificate", "fiscal_certificate"]:
            times = get_processing_time(key)
            assert times["standard"] != "Necunoscut", f"'{key}' nu are timp standard"


class TestVault:
    """Teste pentru seiful personal (vault)."""

    def setup_method(self):
        """Curata vault-ul inainte de fiecare test."""
        clear_vault()

    def test_vault_starts_empty(self):
        fields = get_vault_fields()
        assert fields == {}

    def test_save_single_field(self):
        save_vault_field("LastName", "POPESCU")
        fields = get_vault_fields()
        assert fields["LastName"] == "POPESCU"

    def test_save_multiple_fields(self):
        data = {"LastName": "POPESCU", "FirstName": "Ion", "CNP": "1900101123457"}
        save_vault_fields(data)
        fields = get_vault_fields()
        assert len(fields) == 3
        assert fields["FirstName"] == "Ion"

    def test_overwrite_existing_field(self):
        save_vault_field("LastName", "POPESCU")
        save_vault_field("LastName", "IONESCU")
        fields = get_vault_fields()
        assert fields["LastName"] == "IONESCU"

    def test_clear_vault(self):
        save_vault_fields({"A": "1", "B": "2"})
        clear_vault()
        assert get_vault_fields() == {}
        assert get_vault_documents() == []

    def test_save_vault_document(self):
        doc = {
            "name": "buletin.jpg",
            "rel": "buletin.jpg",
            "type": "identity_card",
            "icon": "ID",
            "fields": {"LastName": "POPESCU", "CNP": "123"},
            "count": 2,
            "source": "single",
        }
        save_vault_document(doc)
        docs = get_vault_documents()
        assert len(docs) == 1
        assert docs[0]["name"] == "buletin.jpg"
        assert docs[0]["fields"]["LastName"] == "POPESCU"

    def test_is_file_in_vault(self):
        doc = {"name": "test.jpg", "rel": "test.jpg", "type": "general",
               "icon": "X", "fields": {}, "count": 0, "source": "single"}
        save_vault_document(doc)
        assert is_file_in_vault("test.jpg") is True
        assert is_file_in_vault("nonexistent.jpg") is False

    def test_folder_scan_tracking(self):
        doc = {"name": "ci.jpg", "rel": "docs/ci.jpg", "type": "identity_card",
               "icon": "ID", "fields": {"CNP": "123"}, "count": 1,
               "source": "folder", "folder": "/home/test/Documents"}
        save_vault_document(doc)
        assert is_folder_scanned("/home/test/Documents") is True
        assert is_folder_scanned("/home/test/Other") is False

    def test_delete_documents_by_folder(self):
        folder = "/tmp/test_folder"
        for i in range(3):
            save_vault_document({
                "name": f"file_{i}.jpg", "rel": f"file_{i}.jpg",
                "type": "general", "icon": "X", "fields": {},
                "count": 0, "source": "folder", "folder": folder
            })
        assert len(get_vault_documents()) == 3
        delete_vault_documents_by_folder(folder)
        assert len(get_vault_documents()) == 0

    def teardown_method(self):
        """Curata dupa fiecare test."""
        clear_vault()


class TestServiceFieldsIntegrity:
    """Teste de integritate intre servicii si campurile lor."""

    def test_total_service_fields_count(self):
        """Verifica numarul total de campuri din toate serviciile."""
        services = get_all_services()
        total = sum(len(svc["required_fields"]) for svc in services.values())
        assert total == 41, f"Asteptat 41 campuri in total, gasit {total}"

    def test_field_keys_are_pascal_case(self):
        """Verifica ca toate cheile de camp sunt in PascalCase."""
        services = get_all_services()
        for key, svc in services.items():
            for field_key in svc["required_fields"]:
                assert field_key[0].isupper(), \
                    f"Cheia '{field_key}' din '{key}' nu incepe cu litera mare"

    def test_cnp_field_present_in_relevant_services(self):
        """CNP-ul trebuie sa fie camp obligatoriu in serviciile relevante."""
        services_with_cnp = ["identity_card", "passport_renewal",
                             "birth_certificate", "fiscal_certificate"]
        all_svcs = get_all_services()
        for key in services_with_cnp:
            assert "CNP" in all_svcs[key]["required_fields"], \
                f"Serviciul '{key}' nu are campul CNP"
