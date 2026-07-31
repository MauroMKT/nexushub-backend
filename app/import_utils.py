"""Parsing generico per l'importazione di record da CSV, JSON o XML.

Nato in Fase 8 solo per l'import Clienti, generalizzato in Fase 9.5 per servire
anche l'import Rubrica (Contatti): entrambi i router passano il proprio set di
alias/campi noti a parse_import_content(), che fa lo stesso lavoro di parsing
e normalizzazione per chiunque lo chiami.

Adattamento a CSV "diversi" (Fase 9.5): prima le colonne del file che non
corrispondevano a un campo noto venivano scartate in silenzio. Ora finiscono
in un dizionario "_extra" per riga, che i router salvano in una colonna
extra_fields (JSON) sul record creato/aggiornato — così un CSV con colonne
impreviste non perde dati, e quelle colonne restano visibili in UI invece di
sparire.
"""
import csv
import io
import json
import xml.etree.ElementTree as ET

# Alias riconosciuti per i campi Cliente, case-insensitive: permette di
# importare file con intestazioni sia in italiano sia in inglese senza che
# l'utente debba rinominare le colonne prima di caricarle.
CLIENT_FIELD_ALIASES = {
    "name": "name", "nome": "name", "nome_completo": "name", "full_name": "name",
    "company": "company", "azienda": "company", "ragione_sociale": "company",
    "email": "email", "e-mail": "email", "posta_elettronica": "email",
    "phone": "phone", "telefono": "phone", "tel": "phone",
    "whatsapp": "whatsapp",
    "sector": "sector", "settore": "sector",
}
CLIENT_KNOWN_FIELDS = ("name", "company", "email", "phone", "whatsapp", "sector")

# Stessa idea per i campi Contatto (Rubrica, Fase 9.5).
CONTACT_FIELD_ALIASES = {
    "full_name": "full_name", "nome": "full_name", "nome_completo": "full_name", "name": "full_name",
    "phone": "phone", "telefono": "phone", "tel": "phone",
    "mobile": "mobile", "cellulare": "mobile",
    "whatsapp": "whatsapp",
    "email": "email", "e-mail": "email", "posta_elettronica": "email",
    "company": "company", "azienda": "company", "ragione_sociale": "company",
    "category": "category", "categoria": "category",
    "notes": "notes", "note": "notes",
}
CONTACT_KNOWN_FIELDS = ("full_name", "phone", "mobile", "whatsapp", "email", "company", "category", "notes")

# Retro-compatibilità: nomi storici usati finora dal router import clienti.
FIELD_ALIASES = CLIENT_FIELD_ALIASES
KNOWN_FIELDS = CLIENT_KNOWN_FIELDS


def _normalize_row(raw: dict, field_aliases: dict) -> tuple[dict, dict]:
    """Mappa le chiavi grezze (qualunque siano maiuscole/minuscole o alias) sui
    campi noti. Le colonne non riconosciute NON vengono più scartate: tornano
    in un secondo dict "extra" così il chiamante può decidere di salvarle."""
    normalized: dict = {}
    extra: dict = {}
    for key, value in raw.items():
        if key is None:
            continue
        key_str = str(key).strip()
        if not key_str:
            continue
        text_val = str(value).strip() if value is not None else ""
        if not text_val:
            continue
        alias = field_aliases.get(key_str.lower())
        if alias:
            normalized[alias] = text_val
        else:
            extra[key_str] = text_val
    return normalized, extra


def parse_import_content(
    fmt: str,
    content: str,
    field_aliases: dict = None,
    known_fields: tuple = None,
    required_any: tuple = ("name", "company"),
    required_fallback_field: str = None,
) -> "tuple[list[dict], list[str]]":
    """Ritorna (righe_normalizzate, errori).

    Ogni riga normalizzata ha i campi noti mappati come chiavi dirette più una
    chiave "_extra" (dict) con le colonne del file che non corrispondevano a
    nessun campo noto. Una riga viene scartata (ed errore aggiunto) solo se
    NESSUNO dei campi in required_any è valorizzato; se required_fallback_field
    è impostato e risulta vuoto, viene riempito col primo campo disponibile
    tra required_any (es. Client.name è NOT NULL: se manca ma c'è "company"
    lo si usa come nome).

    field_aliases/known_fields di default sono quelli Cliente, per compatibilità
    con le chiamate storiche che non li passano esplicitamente.
    """
    field_aliases = field_aliases or CLIENT_FIELD_ALIASES
    fmt = (fmt or "").lower().strip()
    errors: list = []
    raw_rows: list = []

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
        if isinstance(data, list):
            raw_rows = data
        elif isinstance(data, dict):
            # Accetta sia {"clients": [...]}/{"contacts": [...]} sia qualunque
            # altro oggetto con una singola chiave che contiene una lista.
            list_val = next((v for v in data.values() if isinstance(v, list)), None)
            if list_val is None:
                return [], ["Il JSON deve essere una lista di oggetti oppure un oggetto con una chiave che contiene una lista"]
            raw_rows = list_val
        else:
            return [], ["Il JSON deve essere una lista di oggetti oppure un oggetto con una chiave che contiene una lista"]
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

    normalized_rows: list = []
    for i, raw in enumerate(raw_rows, start=1):
        row, extra = _normalize_row(raw, field_aliases)
        if required_any and not any(row.get(f) for f in required_any):
            errors.append(f"Riga {i}: {'/'.join(required_any)} mancante, riga saltata")
            continue
        if required_fallback_field and not row.get(required_fallback_field):
            for f in required_any:
                if row.get(f):
                    row[required_fallback_field] = row[f]
                    break
        row["_extra"] = extra
        normalized_rows.append(row)

    return normalized_rows, errors
