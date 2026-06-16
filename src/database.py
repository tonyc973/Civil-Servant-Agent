# src/database.py — Modul de bază de date SQLite pentru Civil Servant Agent
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "civil_servant.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ── Tabelul serviciilor guvernamentale ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            description TEXT NOT NULL,
            template_file TEXT NOT NULL,
            pdf_enabled INTEGER NOT NULL DEFAULT 1,
            estimated_time TEXT NOT NULL
        )
    """)

    # ── Câmpurile obligatorii per serviciu ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_key TEXT NOT NULL,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (service_key) REFERENCES services(key),
            UNIQUE(service_key, field_key)
        )
    """)

    # ── Registrul cetățenilor (simulat) ────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS citizens (
            cnp TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            dob TEXT NOT NULL,
            status TEXT NOT NULL,
            address TEXT
        )
    """)

    # ── Registrul vehiculelor (simulat) ────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            vin TEXT PRIMARY KEY,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            status TEXT NOT NULL,
            owner_cnp TEXT
        )
    """)

    # ── Programări disponibile ─────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            office TEXT NOT NULL DEFAULT 'Sectorul 1 — Str. Lainici 12'
        )
    """)

    # ── Documente necesare per serviciu ─────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS required_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_key TEXT NOT NULL,
            document_name TEXT NOT NULL,
            doc_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (service_key) REFERENCES services(key)
        )
    """)

    # ── Estimări timp de procesare ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_times (
            service_key TEXT PRIMARY KEY,
            standard_time TEXT NOT NULL,
            urgent_time TEXT NOT NULL,
            FOREIGN KEY (service_key) REFERENCES services(key)
        )
    """)

    # ── Vault personal (persistență documente extrase) ─────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_fields (
            field_key TEXT PRIMARY KEY,
            field_value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rel TEXT NOT NULL,
            doc_type TEXT NOT NULL DEFAULT 'general',
            icon TEXT NOT NULL DEFAULT '📄',
            fields_json TEXT NOT NULL DEFAULT '{}',
            field_count INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'single',
            folder TEXT
        )
    """)

    conn.commit()
    conn.close()


def seed_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Verifică dacă datele sunt deja populate
    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # ── Servicii ───────────────────────────────────────────────────────────
    services = [
        ("identity_card", "Eliberare Carte de Identitate (14 ani)", "🪪",
         "Cerere pentru prima eliberare a cărții de identitate pentru minori.",
         "template_id.pdf", 1, "3–5 zile lucrătoare"),
        ("passport_renewal", "Reînnoire Pașaport", "📘",
         "Cerere de reînnoire a pașaportului electronic expirat.",
         "template_passport.pdf", 1, "5–10 zile lucrătoare"),
        ("vehicle_registration", "Înmatriculare Vehicul", "🚗",
         "Înregistrarea unui vehicul nou achiziționat.",
         "template_vehicle.pdf", 1, "2–3 zile lucrătoare"),
        ("birth_certificate", "Certificat de Naștere", "👶",
         "Solicitare copie oficială certificat de naștere.",
         "template_birth.pdf", 1, "1–2 zile lucrătoare"),
        ("marriage_certificate", "Certificat de Căsătorie", "💍",
         "Eliberare sau copie oficială certificat de căsătorie.",
         "template_marriage.pdf", 1, "2–3 zile lucrătoare"),
        ("fiscal_certificate", "Certificat Fiscal (ANAF)", "🧾",
         "Solicitare certificat de atestare fiscală de la ANAF.",
         "template_fiscal.pdf", 1, "1 zi lucrătoare"),
    ]
    cursor.executemany(
        "INSERT INTO services (key, name, icon, description, template_file, pdf_enabled, estimated_time) VALUES (?,?,?,?,?,?,?)",
        services
    )

    # ── Câmpuri obligatorii ────────────────────────────────────────────────
    fields = {
        "identity_card": [
            ("LastName", "Nume de Familie", 1),
            ("FirstName", "Prenume", 2),
            ("CNP", "Cod Numeric Personal (CNP)", 3),
            ("FatherName", "Prenumele Tatălui", 4),
            ("MotherName", "Prenumele Mamei", 5),
            ("City", "Oraș / Sector", 6),
            ("Street", "Strada", 7),
            ("Number", "Număr", 8),
        ],
        "passport_renewal": [
            ("LastName", "Nume de Familie Actual", 1),
            ("FirstName", "Prenume", 2),
            ("PassportNo", "Număr Pașaport Vechi", 3),
            ("ExpiryDate", "Data Expirării (ZZ/LL/AAAA)", 4),
            ("CNP", "Cod Numeric Personal", 5),
            ("Reason", "Motivul Reînnoirii", 6),
        ],
        "vehicle_registration": [
            ("OwnerName", "Numele Noului Proprietar", 1),
            ("VIN", "Număr Șasiu (VIN)", 2),
            ("CarMake", "Marca Autoturismului", 3),
            ("CarModel", "Modelul Autoturismului", 4),
            ("ProductionYear", "Anul Fabricației", 5),
            ("Date", "Data Achiziției", 6),
        ],
        "birth_certificate": [
            ("ChildLastName", "Numele de Familie al Copilului", 1),
            ("ChildFirstName", "Prenumele Copilului", 2),
            ("CNP", "CNP-ul Copilului", 3),
            ("DateOfBirth", "Data Nașterii (ZZ/LL/AAAA)", 4),
            ("PlaceOfBirth", "Locul Nașterii", 5),
            ("FatherName", "Numele Complet al Tatălui", 6),
            ("MotherName", "Numele Complet al Mamei", 7),
            ("RequestReason", "Motivul Solicitării", 8),
        ],
        "marriage_certificate": [
            ("Spouse1LastName", "Nume Familie Soț/Soție 1", 1),
            ("Spouse1FirstName", "Prenume Soț/Soție 1", 2),
            ("Spouse1CNP", "CNP Soț/Soție 1", 3),
            ("Spouse2LastName", "Nume Familie Soț/Soție 2", 4),
            ("Spouse2FirstName", "Prenume Soț/Soție 2", 5),
            ("Spouse2CNP", "CNP Soț/Soție 2", 6),
            ("MarriageDate", "Data Căsătoriei (ZZ/LL/AAAA)", 7),
            ("MarriageCity", "Orașul Căsătoriei", 8),
        ],
        "fiscal_certificate": [
            ("FullName", "Nume Complet", 1),
            ("CNP", "Cod Numeric Personal (CNP)", 2),
            ("Address", "Adresa de Domiciliu", 3),
            ("RequestDate", "Data Solicitării (ZZ/LL/AAAA)", 4),
            ("Purpose", "Scopul Certificatului", 5),
        ],
    }
    for svc_key, field_list in fields.items():
        for field_key, field_label, order in field_list:
            cursor.execute(
                "INSERT INTO service_fields (service_key, field_key, field_label, field_order) VALUES (?,?,?,?)",
                (svc_key, field_key, field_label, order)
            )

    # ── Cetățeni (registru simulat) ────────────────────────────────────────
    citizens = [
        ("1900101123457", "Ion Popescu", "01/01/1990", "Fără cazier", "Str. Florilor 12, București"),
        ("2950505987655", "Maria Ionescu", "05/05/1995", "Amenzi în curs", "Str. Mihai Eminescu 3, Cluj"),
        ("1850320556786", "Gheorghe Dumitrescu", "20/03/1985", "Fără cazier", "Bd. Unirii 44, Timișoara"),
    ]
    cursor.executemany(
        "INSERT INTO citizens (cnp, name, dob, status, address) VALUES (?,?,?,?,?)",
        citizens
    )

    # ── Vehicule (registru simulat) ────────────────────────────────────────
    vehicles = [
        ("WBAWB73569P019296", "BMW", "320d", 2009, "Înregistrat", "1900101123457"),
        ("VF1RFD00X56789012", "Renault", "Megane", 2015, "Furat", None),
    ]
    cursor.executemany(
        "INSERT INTO vehicles (vin, make, model, year, status, owner_cnp) VALUES (?,?,?,?,?,?)",
        vehicles
    )

    # ── Programări ─────────────────────────────────────────────────────────
    appointments = [
        ("2025-07-14", "09:00", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-14", "10:30", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-14", "14:00", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-15", "09:00", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-15", "11:00", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-15", "15:30", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-16", "10:00", "Sectorul 1 — Str. Lainici 12"),
        ("2025-07-16", "13:00", "Sectorul 1 — Str. Lainici 12"),
    ]
    cursor.executemany(
        "INSERT INTO appointments (date, time, office) VALUES (?,?,?)",
        appointments
    )

    # ── Documente necesare per serviciu ─────────────────────────────────────
    docs = {
        "identity_card": [
            ("Certificat de naștere (original + copie)", 1),
            ("Dovada adresei (factură utilități sau contract de închiriere)", 2),
            ("Cartea de identitate a părintelui/tutorelui", 3),
            ("2 fotografii recente tip pașaport", 4),
            ("Formularul de cerere (generat de acest sistem)", 5),
        ],
        "passport_renewal": [
            ("Pașaportul expirat (original)", 1),
            ("Cartea de identitate validă", 2),
            ("2 fotografii recente tip pașaport (standard biometric)", 3),
            ("Dovada domiciliului", 4),
            ("Formularul de cerere (generat de acest sistem)", 5),
        ],
        "vehicle_registration": [
            ("Dovada achiziției (contract notarial)", 1),
            ("Certificatul de înmatriculare anterior", 2),
            ("Certificat de asigurare (RCA)", 3),
            ("ITP (certificat de inspecție tehnică)", 4),
            ("Cartea de identitate a noului proprietar", 5),
        ],
        "birth_certificate": [
            ("Cărțile de identitate ale părinților", 1),
            ("Scrisoarea de externare din spital (original)", 2),
            ("Certificat de căsătorie (dacă este cazul)", 3),
        ],
        "marriage_certificate": [
            ("Cărțile de identitate ale ambilor soți", 1),
            ("Certificatele de naștere ale ambilor soți", 2),
            ("Declarația prenupțială (notarizată)", 3),
        ],
        "fiscal_certificate": [
            ("Cartea de identitate validă", 1),
            ("Dovada înregistrării fiscale", 2),
        ],
    }
    for svc_key, doc_list in docs.items():
        for doc_name, order in doc_list:
            cursor.execute(
                "INSERT INTO required_documents (service_key, document_name, doc_order) VALUES (?,?,?)",
                (svc_key, doc_name, order)
            )

    # ── Estimări timp de procesare ──────────────────────────────────────────
    times = [
        ("identity_card", "3–5 zile lucrătoare", "24 de ore (se aplică suprataxă)"),
        ("passport_renewal", "5–10 zile lucrătoare", "48 de ore (se aplică suprataxă)"),
        ("vehicle_registration", "2–3 zile lucrătoare", "În aceeași zi"),
        ("birth_certificate", "1–2 zile lucrătoare", "2 ore"),
        ("marriage_certificate", "2–3 zile lucrătoare", "În aceeași zi"),
        ("fiscal_certificate", "1 zi lucrătoare", "2 ore"),
    ]
    cursor.executemany(
        "INSERT INTO processing_times (service_key, standard_time, urgent_time) VALUES (?,?,?)",
        times
    )

    conn.commit()
    conn.close()


# ── Funcții de acces la date ────────────────────────────────────────────────

def get_all_services() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services ORDER BY key")
    services = {}
    for row in cursor.fetchall():
        svc_key = row["key"]
        cursor2 = conn.cursor()
        cursor2.execute(
            "SELECT field_key, field_label FROM service_fields WHERE service_key = ? ORDER BY field_order",
            (svc_key,)
        )
        req_fields = {r["field_key"]: r["field_label"] for r in cursor2.fetchall()}
        services[svc_key] = {
            "name": row["name"],
            "icon": row["icon"],
            "description": row["description"],
            "template_file": row["template_file"],
            "pdf_enabled": bool(row["pdf_enabled"]),
            "estimated_time": row["estimated_time"],
            "required_fields": req_fields,
        }
    conn.close()
    return services


def get_service(key: str) -> dict | None:
    all_svcs = get_all_services()
    return all_svcs.get(key)


def get_citizen(cnp: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM citizens WHERE cnp = ?", (cnp,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"name": row["name"], "dob": row["dob"], "status": row["status"], "address": row["address"]}
    return None


def get_vehicle(vin: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE vin = ?", (vin,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"make": row["make"], "model": row["model"], "year": row["year"],
                "status": row["status"], "owner_cnp": row["owner_cnp"]}
    return None


def get_appointments(limit: int = 5) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT date, time, office FROM appointments ORDER BY date, time LIMIT ?", (limit,))
    slots = [{"date": r["date"], "time": r["time"], "office": r["office"]} for r in cursor.fetchall()]
    conn.close()
    return slots


def get_required_documents(service_key: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT document_name FROM required_documents WHERE service_key = ? ORDER BY doc_order",
        (service_key,)
    )
    docs = [r["document_name"] for r in cursor.fetchall()]
    conn.close()
    return docs


def get_processing_time(service_key: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processing_times WHERE service_key = ?", (service_key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"standard": row["standard_time"], "urgent": row["urgent_time"]}
    return {"standard": "Necunoscut", "urgent": "Necunoscut"}


# ── Vault persistence ──────────────────────────────────────────────────────

def save_vault_field(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO vault_fields (field_key, field_value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def save_vault_fields(fields: dict):
    conn = get_connection()
    for k, v in fields.items():
        conn.execute(
            "INSERT OR REPLACE INTO vault_fields (field_key, field_value) VALUES (?, ?)",
            (k, str(v))
        )
    conn.commit()
    conn.close()


def get_vault_fields() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT field_key, field_value FROM vault_fields")
    result = {r["field_key"]: r["field_value"] for r in cursor.fetchall()}
    conn.close()
    return result


def clear_vault():
    conn = get_connection()
    conn.execute("DELETE FROM vault_fields")
    conn.execute("DELETE FROM vault_documents")
    conn.commit()
    conn.close()


def save_vault_document(doc: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO vault_documents (name, rel, doc_type, icon, fields_json, field_count, source, folder)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            doc.get("name", ""),
            doc.get("rel", ""),
            doc.get("type", "general"),
            doc.get("icon", "📄"),
            json.dumps(doc.get("fields", {}), ensure_ascii=False),
            doc.get("count", 0),
            doc.get("source", "single"),
            doc.get("folder"),
        )
    )
    conn.commit()
    conn.close()


def get_vault_documents() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vault_documents ORDER BY id")
    docs = []
    for r in cursor.fetchall():
        docs.append({
            "id": r["id"],
            "name": r["name"],
            "rel": r["rel"],
            "type": r["doc_type"],
            "icon": r["icon"],
            "fields": json.loads(r["fields_json"]),
            "count": r["field_count"],
            "source": r["source"],
            "folder": r["folder"],
        })
    conn.close()
    return docs


def delete_vault_documents_by_folder(folder: str):
    conn = get_connection()
    conn.execute("DELETE FROM vault_documents WHERE folder = ?", (folder,))
    conn.commit()
    conn.close()


def is_folder_scanned(folder: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vault_documents WHERE folder = ?", (folder,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def is_file_in_vault(filename: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vault_documents WHERE name = ?", (filename,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0



# ── Inițializare automată ──────────────────────────────────────────────────
init_db()
seed_db()
