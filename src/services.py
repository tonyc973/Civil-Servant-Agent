# src/services.py — Registrul de Servicii (date din SQLite)
from src.database import get_all_services

# Încarcă serviciile din baza de date SQLite.
# Structura returnată este identică cu cea anterioară (dict de dict-uri)
# pentru compatibilitate cu restul aplicației.
SERVICES = get_all_services()
