# src/mcp_server.py — Enhanced MCP Server with multiple tools
import json
import re
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CitizenRegistry")

# ─── Simulated Databases ────────────────────────────────────────────────────
CITIZEN_DB = {
    "1900101123456": {"name": "Ion Popescu", "dob": "01/01/1990", "status": "Clean Record", "address": "Str. Florilor 12, București"},
    "2950505987654": {"name": "Maria Ionescu", "dob": "05/05/1995", "status": "Pending Fines", "address": "Str. Mihai Eminescu 3, Cluj"},
    "1850320556789": {"name": "Gheorghe Dumitrescu", "dob": "20/03/1985", "status": "Clean Record", "address": "Bd. Unirii 44, Timișoara"},
}

VEHICLE_DB = {
    "WBAWB73569P019296": {"make": "BMW", "model": "320d", "year": 2009, "status": "Registered", "owner_cnp": "1900101123456"},
    "VF1RFD00X56789012": {"make": "Renault", "model": "Megane", "year": 2015, "status": "Stolen", "owner_cnp": None},
}

APPOINTMENT_SLOTS = {
    "2025-07-14": ["09:00", "10:30", "14:00"],
    "2025-07-15": ["09:00", "11:00", "15:30"],
    "2025-07-16": ["10:00", "13:00"],
}

# ─── Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_cnp(cnp: str) -> str:
    """
    Validates a 13-digit Romanian Personal Numerical Code (CNP).
    Returns citizen identity details if found in the national registry.
    Performs checksum validation even for unknown CNPs.
    """
    cnp = cnp.strip()
    if not re.match(r"^\d{13}$", cnp):
        return json.dumps({"valid": False, "error": "CNP must be exactly 13 digits."})

    # Romanian CNP checksum algorithm
    weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
    checksum = sum(int(cnp[i]) * weights[i] for i in range(12)) % 11
    expected_digit = 1 if checksum == 10 else checksum
    if int(cnp[12]) != expected_digit:
        return json.dumps({"valid": False, "error": "Invalid CNP checksum. The number does not conform to the national standard."})

    if cnp in CITIZEN_DB:
        return json.dumps({"valid": True, "data": CITIZEN_DB[cnp]})

    # Decode embedded metadata from CNP
    gender_digit = int(cnp[0])
    gender = "Male" if gender_digit in [1, 3, 5, 7] else "Female"
    century_map = {1: "19", 2: "19", 3: "18", 4: "18", 5: "20", 6: "20"}
    century = century_map.get(gender_digit, "20")
    dob = f"{cnp[5:7]}/{cnp[3:5]}/{century}{cnp[1:3]}"

    return json.dumps({
        "valid": True,
        "data": {
            "name": "Unknown Citizen",
            "dob": dob,
            "gender": gender,
            "status": "Not in local registry — valid checksum",
        },
    })


@mcp.tool()
def check_vehicle_status(vin: str) -> str:
    """
    Looks up a Vehicle Identification Number (VIN) in the national vehicle registry.
    Returns ownership, make/model, year, and legal status (e.g., stolen, registered).
    """
    vin = vin.strip().upper()
    if vin in VEHICLE_DB:
        return json.dumps({"found": True, "data": VEHICLE_DB[vin]})
    return json.dumps({"found": False, "message": "VIN not found in registry. Proceed with manual verification."})


@mcp.tool()
def get_available_appointments(service_type: str) -> str:
    """
    Retrieves available appointment slots for a given government service type.
    Returns a list of available dates and times at the nearest office.
    """
    slots = []
    for date, times in APPOINTMENT_SLOTS.items():
        for time in times:
            slots.append({"date": date, "time": time, "office": "Sector 1 — Str. Lainici 12"})
    return json.dumps({
        "service": service_type,
        "available_slots": slots[:5],
        "note": "Slots are first-come, first-served. Bring all original documents.",
    })


@mcp.tool()
def estimate_processing_time(service_type: str, is_urgent: bool = False) -> str:
    """
    Returns the estimated processing time for a given service type.
    Supports an urgent processing flag for expedited handling.
    """
    estimates = {
        "identity_card": {"standard": "3–5 business days", "urgent": "24 hours (surcharge applies)"},
        "passport_renewal": {"standard": "5–10 business days", "urgent": "48 hours (surcharge applies)"},
        "vehicle_registration": {"standard": "2–3 business days", "urgent": "Same day"},
        "birth_certificate": {"standard": "1–2 business days", "urgent": "2 hours"},
        "marriage_certificate": {"standard": "2–3 business days", "urgent": "Same day"},
        "fiscal_certificate": {"standard": "1 business day", "urgent": "2 hours"},
    }
    svc = estimates.get(service_type, {"standard": "Unknown", "urgent": "Unknown"})
    mode = "urgent" if is_urgent else "standard"
    return json.dumps({
        "service": service_type,
        "mode": mode,
        "estimated_time": svc[mode],
        "fee_note": "Urgent processing requires an additional fee payable at the office.",
    })


@mcp.tool()
def check_required_documents(service_type: str) -> str:
    """
    Returns the official checklist of physical documents required to complete
    a government service application in person.
    """
    docs = {
        "identity_card": [
            "Birth certificate (original + copy)",
            "Proof of address (utility bill or lease agreement)",
            "Parent/guardian ID card",
            "2 recent passport-style photos",
            "Application form (generated by this system)",
        ],
        "passport_renewal": [
            "Expired passport (original)",
            "Current valid ID card",
            "2 recent passport-style photos (biometric standard)",
            "Proof of residency",
            "Application form (generated by this system)",
        ],
        "vehicle_registration": [
            "Proof of purchase (notarized contract)",
            "Previous registration certificate",
            "Insurance certificate (RCA)",
            "ITP (technical inspection certificate)",
            "ID card of new owner",
        ],
        "birth_certificate": [
            "Parent ID cards",
            "Hospital discharge summary (original)",
            "Marriage certificate (if applicable)",
        ],
        "marriage_certificate": [
            "Both spouses' ID cards",
            "Birth certificates of both spouses",
            "Prenuptial declaration (notarized)",
        ],
        "fiscal_certificate": [
            "Valid ID card",
            "Tax registration proof",
        ],
    }
    return json.dumps({
        "service": service_type,
        "required_documents": docs.get(service_type, ["Please contact your local office for the document list."]),
    })

if __name__ == "__main__":
    mcp.run()