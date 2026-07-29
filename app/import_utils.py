"""Parsing per l'importazione clienti da CSV, JSON o XML (Fase 8).

Ogni formato viene normalizzato nello stesso elenco di dict con chiavi note
(name, company, email, phone, whatsapp, sector) prima di essere passato al router,
che si occupa poi di creare/aggiornare i record Client.
"""
import csv
import io
import json
import xml.etree.ElementTree as ET

# Alias riconosciuti per ogni campo, case-insensitive: permette di importare file
# con intestazioni sia in italiano sia in inglese senza che l'utente debba
# rinominare le colonne prima di caricarle.
FIELD_ALIASES = {
    "name": "name", "nome": "name", "nome_completo": "name", "full_name": "name",
    "company": "company", "azienda": "company", "ragione_sociale": "company",
    "email": "email", "e-mail": "email", "posta_elettronica": "email",
    "phone": "phone", "telefono": "phone", "tel": "phone",
    "whatsapp": "whatsapp",
    "sector": "sector", "settore": "sector",
}

KNOWN_FIELDS = ("name", "company", "email", "phone", "whatsapp", "sector")


def _normalize_row(raw: dict) -> dict:
    """Mappa le chiavi grezze (qualunque siano maiuscole/minuscole o alias) sui
    campi noti; ignora tutte le colonne non riconosciute."""
    normalized = {}
    for key, value in raw.items():
        if key is None:
            continue
        alias = FIELD_ALIASES.get(str(key).strip().lower())
        if alias and value is not None:
            text = str(value).strip()
            if text:
                normalized[alias] = text
    return normalized


def parse_import_content(fmt: str, content: str) -> tuple[list[dict], list[str]]:
    """Ritorna (righe_normalizzate, errori). Le righe senza 'name' né 'company'
    vengono scartate e segnalate come errore (Client.name è obbligatorio in DB)."""
    fmt = (fmt or "").lower().strip()
    errors: list[str] = []
    raw_rows: list[dict] = []

    if fmt == "csv":
        try:
            reader = csv.DictReader(io.StringIO(content))
            raw_rows = [dict(r) for r in reader]
        except csv.Error as e:
            return [], [f"CSV non valido: {e}"]

    elif fmt == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return [], [f"JSON non valido: {e}"]
        if isinstance(data, dict) and isinstance(data.get("clients"), list):
            raw_rows = data["clients"]
        elif isinstance(data, list):
            raw_rows = data
        else:
            return [], ["Il JSON deve essere una lista di oggetti oppure un oggetto con chiave \"clients\""]
        raw_rows = [r for r in raw_rows if isinstance(r, dict)]

    elif fmt == "xml":
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return [], [f"XML non valido: {e}"]
        for child in root:
            row = {}
            for field_el in child:
                if field_el.text:
                    row[field_el.tag] = field_el.text
            # Attributi dell'elemento (es. <client name="..."/>) supportati come fallback
            for attr_key, attr_val in child.attrib.items():
                row.setdefault(attr_key, attr_val)
            raw_rows.append(row)

    else:
        return [], [f"Formato non supportato: {fmt} (atteso csv, json o xml)"]

    normalized_rows: list[dict] = []
    for i, raw in enumerate(raw_rows, start=1):
        row = _normalize_row(raw)
        if not row.get("name") and not row.get("company"):
            errors.append(f"Riga {i}: nome o azienda mancante, riga saltata")
            continue
        if not row.get("name"):
            row["name"] = row["company"]
        normalized_rows.append(row)

    return normalized_rows, errors
