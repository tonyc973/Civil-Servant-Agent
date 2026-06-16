# src/vault_agent.py — Agent pentru Seiful Personal de Documente v2
#
# Pipeline unic pentru orice document, indiferent de sursă:
#       rasterizează (dacă e PDF) → clasifică → sari peste pagini goale →
#       extrage câmpuri → normalizează la chei canonice → îmbină în seif.
#
# Două puncte de intrare publice, ambele construite peste același pipeline:
#   • extract_from_file(file)            — un singur fișier (imagine / PDF 1 pagină)
#   • scan_folder(path, cb)              — un folder local întreg (imagini + PDF-uri)
#
# Folosește GPT-4o Vision. Cheile sunt normalizate la forma canonică de formular,
# ca să auto-completeze oricare dintre cele 6 formulare guvernamentale.

import os
import io
import json
import base64
import tempfile
import subprocess
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

VISION_MODEL = "gpt-4o"

# ── Maparea cheilor de câmp către forma canonică ──────────────────────────────
CANONICAL_MAP = {
    # Nume
    "last_name": "LastName", "family_name": "LastName", "surname": "LastName",
    "nume": "LastName", "nume_familie": "LastName",
    "first_name": "FirstName", "given_name": "FirstName",
    "prenume": "FirstName", "forename": "FirstName",
    "full_name": "FullName", "name": "FullName",

    # Identitate
    "cnp": "CNP", "personal_code": "CNP", "cod_numeric_personal": "CNP",
    "personal_numerical_code": "CNP",
    "passport_number": "PassportNo", "passport_no": "PassportNo",
    "no_pasaport": "PassportNo",
    "id_number": "IDNumber", "card_number": "IDNumber",

    # Părinți
    "father_name": "FatherName", "fathers_name": "FatherName",
    "tata": "FatherName", "father": "FatherName",
    "mother_name": "MotherName", "mothers_name": "MotherName",
    "mama": "MotherName", "mother": "MotherName",

    # Adresă
    "city": "City", "oras": "City", "localitate": "City", "sector": "City",
    "municipality": "City", "town": "City",
    "street": "Street", "strada": "Street", "street_name": "Street",
    "street_number": "Number", "numar": "Number", "number": "Number",
    "house_number": "Number",
    "address": "Address", "adresa": "Address",

    # Vehicul
    "vin": "VIN", "chassis": "VIN", "chassis_number": "VIN",
    "serie_sasiu": "VIN", "numar_sasiu": "VIN",
    "car_make": "CarMake", "make": "CarMake", "brand": "CarMake", "marca": "CarMake",
    "car_model": "CarModel", "model": "CarModel",
    "year": "ProductionYear", "production_year": "ProductionYear",
    "an_fabricatie": "ProductionYear", "year_of_manufacture": "ProductionYear",
    "owner_name": "OwnerName", "proprietar": "OwnerName",

    # Date calendaristice
    "date_of_birth": "DateOfBirth", "dob": "DateOfBirth",
    "birth_date": "DateOfBirth", "data_nasterii": "DateOfBirth",
    "expiry_date": "ExpiryDate", "expires": "ExpiryDate",
    "expiration_date": "ExpiryDate", "valid_until": "ExpiryDate",
    "data_expirarii": "ExpiryDate",
    "marriage_date": "MarriageDate", "data_casatoriei": "MarriageDate",
    "date_of_marriage": "MarriageDate",
    "request_date": "RequestDate", "data_solicitarii": "RequestDate",
    "purchase_date": "Date", "date": "Date",

    # Altele
    "place_of_birth": "PlaceOfBirth", "birth_place": "PlaceOfBirth",
    "locul_nasterii": "PlaceOfBirth",
    "marriage_city": "MarriageCity", "oras_casatorie": "MarriageCity",
    "child_first_name": "ChildFirstName", "child_last_name": "ChildLastName",
    "spouse1_first_name": "Spouse1FirstName", "spouse1_last_name": "Spouse1LastName",
    "spouse1_cnp": "Spouse1CNP",
    "spouse2_first_name": "Spouse2FirstName", "spouse2_last_name": "Spouse2LastName",
    "spouse2_cnp": "Spouse2CNP",
    "purpose": "Purpose", "reason": "Purpose",
    "request_reason": "RequestReason",
}

DOCUMENT_TYPE_HINTS = {
    "identity_card": (
        "Romanian Identity Card (CI/BI). "
        "Extract: cnp, last_name, first_name, date_of_birth, address, city, street, street_number. "
        "Father/mother names are NOT on the front of a standard CI — only extract them if explicitly printed."
    ),
    "passport": (
        "Romanian Passport. "
        "Extract: passport_number, last_name, first_name, cnp, date_of_birth, expiry_date."
    ),
    "birth_certificate": (
        "Romanian Birth Certificate (certificat de nastere). "
        "Extract: child_first_name, child_last_name, cnp, date_of_birth, place_of_birth, father_name, mother_name."
    ),
    "vehicle_doc": (
        "Vehicle registration certificate or purchase contract. "
        "Extract: vin, car_make, car_model, production_year, owner_name, purchase_date."
    ),
    "utility_bill": (
        "Utility bill used as address proof. "
        "Extract: full_name, address, city, street, street_number."
    ),
    "marriage_certificate": (
        "Marriage certificate (certificat de casatorie). "
        "Extract: spouse1_first_name, spouse1_last_name, spouse1_cnp, "
        "spouse2_first_name, spouse2_last_name, spouse2_cnp, marriage_date, marriage_city."
    ),
    "general": (
        "Personal identity or civil document. "
        "Extract every personal data field you can find."
    ),
    "blank_or_irrelevant": "",
}

SKIP_TYPES = {"blank_or_irrelevant", "blank", "irrelevant", "empty", "cover", "divider"}

TYPE_ICONS = {
    "identity_card": "🪪",
    "passport": "📘",
    "birth_certificate": "👶",
    "vehicle_doc": "🚗",
    "utility_bill": "🏠",
    "marriage_certificate": "💍",
    "general": "📄",
    "blank_or_irrelevant": "⬜",
}

SKIP_PHRASES = {"null", "none", "n/a", "not provided", "unknown", "not available", ""}


class VaultAgent:
    """
    Agent AI pentru Seiful Personal de Documente.

    Puncte de intrare:
        extract_from_file(file)        — un fișier (imagine sau PDF cu o pagină)
        scan_folder(path, cb)          — un folder local întreg
    """

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set.")
        self.client = OpenAI(api_key=api_key)

    # ── Primitive Vision ────────────────────────────────────────────────────────

    @staticmethod
    def _b64_url(data: bytes, media_type: str = "image/jpeg") -> str:
        return f"data:{media_type};base64,{base64.b64encode(data).decode()}"

    def _vision_json(self, image_url: str, prompt: str, max_tokens: int = 700) -> dict:
        """Trimite o imagine + prompt la GPT-4o Vision și întoarce JSON-ul parsat."""
        try:
            resp = self.client.chat.completions.create(
                model=VISION_MODEL,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }],
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            return {"_error": str(e)}

    @staticmethod
    def _normalize(raw: dict) -> dict:
        """Filtrează valorile goale/placeholder și mapează cheile la forma canonică."""
        out = {}
        for k, v in raw.items():
            if not v or str(v).strip().lower() in SKIP_PHRASES:
                continue
            key = k.lower().strip().replace(" ", "_").replace("-", "_")
            canonical = CANONICAL_MAP.get(key)
            if canonical:
                out[canonical] = str(v).strip()
        return out

    @staticmethod
    def _merge(dst: dict, src: dict) -> None:
        """Adaugă câmpurile din src în dst; la conflict câștigă valoarea deja prezentă."""
        for k, v in src.items():
            dst.setdefault(k, v)

    # ── Utilitare PDF ─────────────────────────────────────────────────────────────

    @staticmethod
    def _page_count(pdf_bytes: bytes) -> int:
        try:
            from pypdf import PdfReader
            return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
        except Exception:
            return 0

    @staticmethod
    def _rasterize(pdf_bytes: bytes, dpi: int = 150) -> list:
        """Întoarce o listă de bytes JPEG, câte unul per pagină, prin pdftoppm."""
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "in.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            prefix = os.path.join(tmp, "pg")
            r = subprocess.run(
                ["pdftoppm", "-jpeg", "-r", str(dpi), pdf_path, prefix],
                capture_output=True,
            )
            if r.returncode != 0:
                raise RuntimeError(f"pdftoppm: {r.stderr.decode()}")
            files = sorted(Path(tmp).glob("pg-*.jpg"))
            return [f.read_bytes() for f in files]

    # ── Clasificare + extragere (o singură imagine) ───────────────────────────────

    def _classify(self, image_url: str) -> str:
        prompt = (
            "Classify this page into exactly one of these document types:\n"
            "identity_card, passport, birth_certificate, vehicle_doc, "
            "utility_bill, marriage_certificate, general, blank_or_irrelevant\n\n"
            "- blank_or_irrelevant: empty pages, covers, dividers, non-personal-document content\n"
            "- general: clearly personal document but doesn't match the others\n\n"
            'Reply ONLY with JSON: {"type": "<type_here>"}'
        )
        result = self._vision_json(image_url, prompt, max_tokens=30)
        doc_type = result.get("type", "general").strip().lower()
        return doc_type if doc_type in DOCUMENT_TYPE_HINTS else "general"

    def _extract(self, image_bytes: bytes, doc_type: str, mt: str = "image/jpeg") -> dict:
        hint = DOCUMENT_TYPE_HINTS.get(doc_type, DOCUMENT_TYPE_HINTS["general"])
        prompt = f"""You are a government document OCR specialist.

Document type: {doc_type.upper().replace("_", " ")}
{hint}

STRICT RULES:
1. Extract ONLY text explicitly visible on this document.
2. Return null for missing fields — never "N/A" or placeholder text.
3. Dates must be DD/MM/YYYY.
4. Preserve exact capitalisation of names.
5. Return a flat JSON object with snake_case keys.

Example: {{"last_name": "POPESCU", "first_name": "Ion", "cnp": "1900101123456"}}"""
        raw = self._vision_json(self._b64_url(image_bytes, mt), prompt)
        return raw if "_error" in raw else self._normalize(raw)

    def _scan_image(self, image_bytes: bytes, page: int, mt: str = "image/jpeg",
                    progress=None, label: str = "page") -> dict:
        """Clasifică o imagine și, dacă nu e goală, îi extrage câmpurile.

        Inima comună a tuturor punctelor de intrare. Întoarce un page-record uniform:
            {page, type, icon, fields, skipped, error}
        `progress(msg)` (opțional) e apelat pentru pașii vizibili: clasificare, extragere.
        """
        if progress:
            progress(f"Classifying {label}…")
        doc_type = self._classify(self._b64_url(image_bytes, mt))
        rec = {
            "page": page,
            "type": doc_type,
            "icon": TYPE_ICONS.get(doc_type, "📄"),
            "fields": {},
            "skipped": doc_type in SKIP_TYPES,
            "error": None,
        }
        if rec["skipped"]:
            return rec

        if progress:
            progress(f"Extracting {label} ({doc_type.replace('_', ' ')})…")
        fields = self._extract(image_bytes, doc_type, mt)
        if "_error" in fields:
            rec["error"] = fields["_error"]
        else:
            rec["fields"] = fields
        return rec

    # ── Punct de intrare: un singur fișier ────────────────────────────────────────

    def detect_document_type(self, uploaded_file) -> str:
        data = uploaded_file.getvalue()
        mt = "image/png" if uploaded_file.name.lower().endswith(".png") else "image/jpeg"
        return self._classify(self._b64_url(data, mt))

    def extract_from_file(self, uploaded_file, doc_type: str = None) -> dict:
        """Extragere dintr-un singur fișier (imagine sau PDF cu o pagină)."""
        data = uploaded_file.getvalue()
        name = uploaded_file.name.lower()

        if name.endswith(".pdf"):
            try:
                pages = self._rasterize(data)
            except Exception as e:
                return {"_error": str(e)}
            if not pages:
                return {"_error": "PDF produced no pages"}
            image_bytes, mt = pages[0], "image/jpeg"
        else:
            image_bytes = data
            mt = "image/png" if name.endswith(".png") else "image/jpeg"

        if not doc_type:
            doc_type = self._classify(self._b64_url(image_bytes, mt))
        return self._extract(image_bytes, doc_type, mt)


    # ── Punct de intrare: folder local recursiv ───────────────────────────────────

    def walk_folder(self, folder_path: str) -> list:
        """Parcurge recursiv un director și întoarce fișierele suportate (ignoră ascunse).

        [{"path": Path, "rel": str, "ext": str}, ...]
        """
        root = Path(folder_path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder_path}")

        files = []
        for p in sorted(root.rglob("*")):
            if any(part.startswith(".") for part in p.parts):  # sari peste ascunse (.git, .DS_Store)
                continue
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append({"path": p, "rel": str(p.relative_to(root)), "ext": p.suffix.lower()})
        return files

    def scan_folder(self, folder_path: str, progress_callback=None) -> dict:
        """Scanează recursiv un folder local după documente personale.

        Imaginile sunt clasificate + extrase direct; PDF-urile sunt rasterizate și
        procesate pagină cu pagină. Câmpurile fiecărui fișier se îmbină într-un seif
        global (la conflict câștigă primul fișier).

        progress_callback(current, total, status_msg, file_result_or_None)

        Întoarce: {vault, files, total_files, total_pages, skipped_files,
                   total_fields, error}
        """
        try:
            files = self.walk_folder(folder_path)
        except Exception as e:
            return _err_result(str(e))
        if not files:
            return _err_result("No supported files found (jpg, png, pdf).")

        vault, results = {}, []
        total_pages = skipped_files = 0
        total = len(files)

        for idx, info in enumerate(files):
            path, rel, ext = info["path"], info["rel"], info["ext"]

            def notify(msg, rec=None, cur=idx + 1):
                if progress_callback:
                    progress_callback(cur, total, msg, rec)

            notify(f"Reading {rel}…")
            fr = {"rel": rel, "name": path.name, "pages": [], "fields": {},
                  "skipped": False, "error": None, "source": "folder",
                  "type": "general", "icon": "📄"}

            try:
                raw = path.read_bytes()
            except Exception as e:
                fr["error"], fr["skipped"] = str(e), True
                skipped_files += 1
                results.append(fr)
                continue

            if ext == ".pdf":
                try:
                    images = self._rasterize(raw, dpi=150)
                except Exception as e:
                    fr["error"], fr["skipped"] = f"Rasterization failed: {e}", True
                    skipped_files += 1
                    results.append(fr)
                    continue
                for i, img in enumerate(images):
                    total_pages += 1
                    rec = self._scan_image(img, i + 1, progress=notify,
                                           label=f"{rel} p.{i + 1}/{len(images)}")
                    fr["pages"].append(rec)
                    self._merge(fr["fields"], rec["fields"])
                # Tipul fișierului = cel mai frecvent tip ne-gol dintre pagini.
                types = [p["type"] for p in fr["pages"] if not p["skipped"]]
                fr["type"] = max(set(types), key=types.count) if types else "general"
                fr["icon"] = TYPE_ICONS.get(fr["type"], "📄")
            else:
                total_pages += 1
                mt = "image/png" if ext == ".png" else "image/jpeg"
                rec = self._scan_image(raw, 1, mt, progress=notify, label=rel)
                fr["type"], fr["icon"], fr["error"] = rec["type"], rec["icon"], rec["error"]
                if rec["skipped"]:
                    fr["skipped"] = True
                    skipped_files += 1
                else:
                    fr["fields"] = rec["fields"]

            self._merge(vault, fr["fields"])
            results.append(fr)
            n = len(fr["fields"])
            notify(f"✓ {rel} — {n} field{'s' if n != 1 else ''} extracted", fr)

        return {"vault": vault, "files": results, "total_files": total,
                "total_pages": total_pages, "skipped_files": skipped_files,
                "total_fields": len(vault), "error": None}

    # ── Auto-completare formular ──────────────────────────────────────────────────

    def auto_fill_form(self, vault: dict, required_fields: dict) -> dict:
        filled, missing = {}, {}
        for key, label in required_fields.items():
            value = self._lookup_in_vault(vault, key)
            if value:
                filled[key] = value
            else:
                missing[key] = label
        return {"filled": filled, "missing": missing}

    def _lookup_in_vault(self, vault: dict, key: str):
        """Caută în seif cu mapare inteligentă: sinonime, compoziție/decompoziție
        FullName ↔ FirstName + LastName. Returnează None dacă nu găsește."""
        if vault.get(key):
            return vault[key]

        synonyms = {
            "FullName":  ["OwnerName"],
            "OwnerName": ["FullName"],
        }
        for syn in synonyms.get(key, []):
            if vault.get(syn):
                return vault[syn]

        # Compoziție: FullName / OwnerName din FirstName + LastName.
        if key in ("FullName", "OwnerName"):
            first = (vault.get("FirstName") or "").strip()
            last  = (vault.get("LastName")  or "").strip()
            if first and last:
                # Convenția OwnerName în registru: "NUME Prenume" (LAST first, caps).
                if key == "OwnerName":
                    return f"{last.upper()} {first}"
                return f"{first} {last}"

        # Decompoziție: FirstName / LastName din FullName sau OwnerName.
        if key in ("FirstName", "LastName"):
            full = (vault.get("FullName") or vault.get("OwnerName") or "").strip()
            if full:
                parts = full.split(None, 1)
                if len(parts) == 2:
                    # Dacă primul cuvânt e tot majuscule, formatul e "LAST First"
                    # (convenția OwnerName); altfel e "First Last" (FullName).
                    if parts[0].isupper():
                        last, first = parts[0], parts[1]
                    else:
                        first, last = parts[0], parts[1]
                    return last if key == "LastName" else first

        return None


# ── ajutător ─────────────────────────────────────────────────────────────────────
def _err_result(msg: str) -> dict:
    return {"vault": {}, "pages": [], "total_pages": 0,
            "processed_pages": 0, "total_fields": 0, "error": msg}
