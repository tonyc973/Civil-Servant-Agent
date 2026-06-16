# src/mcp_server.py — Server MCP cu instrumente multiple (date din SQLite)
import json
import re
import os
import sys
from datetime import datetime
from mcp.server.fastmcp import FastMCP
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.database import get_citizen, get_vehicle, get_appointments, get_required_documents, get_processing_time

mcp = FastMCP("RegistruCetateni")


@mcp.tool()
def verify_cnp(cnp: str) -> str:
    """
    Verifică un Cod Numeric Personal (CNP) în registrul național.
    Validează formatul, suma de control și caută în baza de date.
    """
    cnp = cnp.strip()
    if not re.match(r"^\d{13}$", cnp):
        return json.dumps({"valid": False, "error": "CNP-ul trebuie să conțină exact 13 cifre."})

    # Verificare sumă de control
    weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
    checksum = sum(int(cnp[i]) * weights[i] for i in range(12)) % 11
    expected_digit = 1 if checksum == 10 else checksum
    if int(cnp[12]) != expected_digit:
        return json.dumps({"valid": False, "error": "Sumă de control invalidă. Numărul nu respectă standardul național."})

    # Validare dată de naștere
    gender_digit = int(cnp[0])
    if gender_digit not in [1, 2, 3, 4, 5, 6, 7, 8]:
        return json.dumps({"valid": False, "error": "CNP invalid: prima cifră trebuie să fie între 1 și 8."})

    century_map = {1: "19", 2: "19", 3: "18", 4: "18", 5: "20", 6: "20", 7: "19", 8: "19"}
    century = century_map[gender_digit]

    year = int(century + cnp[1:3])
    month = int(cnp[3:5])
    day = int(cnp[5:7])

    if not (1 <= month <= 12):
        return json.dumps({"valid": False, "error": f"CNP invalid: luna {month} nu există."})

    import calendar
    max_day = calendar.monthrange(year, month)[1]
    if not (1 <= day <= max_day):
        return json.dumps({"valid": False, "error": f"CNP invalid: ziua {day} nu există în luna {month}/{year}."})

    # Căutare în baza de date SQLite
    citizen = get_citizen(cnp)
    if citizen:
        return json.dumps({"valid": True, "data": citizen})

    # Decodare metadate pentru CNP-uri necunoscute
    gender = "Masculin" if gender_digit in [1, 3, 5, 7] else "Feminin"
    dob = f"{day:02d}/{month:02d}/{year}"

    return json.dumps({
        "valid": True,
        "data": {
            "name": "Cetățean Necunoscut",
            "dob": dob,
            "gender": gender,
            "status": "Nu figurează în registrul local — sumă de control validă",
        },
    })


@mcp.tool()
def check_vehicle_status(vin: str) -> str:
    """
    Caută un Număr de Identificare a Vehiculului (VIN) în registrul național.
    Returnează proprietarul, marca/modelul, anul și statusul legal.
    """
    vin = vin.strip().upper()
    vehicle = get_vehicle(vin)
    if vehicle:
        return json.dumps({"found": True, "data": vehicle})
    return json.dumps({"found": False, "message": "VIN-ul nu a fost găsit în registru. Procedați cu verificare manuală."})


@mcp.tool()
def get_available_appointments(service_type: str) -> str:
    """
    Obține programările disponibile pentru un serviciu guvernamental.
    Returnează o listă de date și ore disponibile la cel mai apropiat birou.
    """
    slots = get_appointments(limit=5)
    return json.dumps({
        "service": service_type,
        "available_slots": slots,
        "note": "Programările se acordă în ordinea sosirii. Aduceți toate documentele originale.",
    })


@mcp.tool()
def estimate_processing_time(service_type: str, is_urgent: bool = False) -> str:
    """
    Returnează timpul estimat de procesare pentru un tip de serviciu.
    Suportă procesare urgentă pentru gestionare accelerată.
    """
    times = get_processing_time(service_type)
    mode = "urgent" if is_urgent else "standard"
    estimated = times["urgent"] if is_urgent else times["standard"]
    return json.dumps({
        "service": service_type,
        "mode": mode,
        "estimated_time": estimated,
        "fee_note": "Procesarea urgentă necesită o taxă suplimentară plătibilă la ghișeu.",
    })


@mcp.tool()
def check_required_documents(service_type: str) -> str:
    """
    Returnează lista oficială de documente fizice necesare pentru
    completarea unei cereri de serviciu guvernamental.
    """
    docs = get_required_documents(service_type)
    if not docs:
        docs = ["Vă rugăm contactați biroul local pentru lista de documente."]
    return json.dumps({
        "service": service_type,
        "required_documents": docs,
    })


if __name__ == "__main__":
    mcp.run()
