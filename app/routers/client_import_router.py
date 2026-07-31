"""Import clienti da CSV, JSON o XML (Fase 8, esteso Fase 9.5 con extra_fields
e Fase 9.6 con note + scrittura collegata in Rubrica).

Due step distinti, coerenti col resto dell'app (niente sorprese: l'utente vede
sempre un'anteprima prima di scrivere in DB):
- POST /clients/import/preview: parsing + validazione, nessuna scrittura.
- POST /clients/import/commit: stesso parsing, poi crea/aggiorna i Client.
  Il match dei duplicati è per email (dentro lo stesso tenant, e solo se il
  valore assomiglia davvero a un'email — vedi import_utils.looks_like_email):
  se duplicate_strategy == "update" un cliente con la stessa email viene
  aggiornato, altrimenti la riga viene saltata.

Fase 9.5: le colonne del CSV/JSON/XML che non corrispondono a name/company/
email/phone/whatsapp/sector/notes non vengono più scartate — finiscono in
Client.extra_fields (JSON) così il CRM "si adatta" a un file con colonne
diverse invece di perdere quei dati.

Fase 9.6: ogni cliente creato o aggiornato da questo import crea/aggiorna
automaticamente anche un contatto collegato in Rubrica (category="cliente",
client_id=client.id) — così un solo import popola sia la pagina Clienti sia
la Rubrica, per qualunque tenant, senza dover ripetere l'import due volte.
Questo comportamento è quello per cui esisteva già "Importa dai clienti"
nella Rubrica (contacts_router.py): qui lo stesso collegamento avviene subito,
in un solo passaggio.
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..import_utils import CLIENT_FIELD_ALIASES, CLIENT_KNOWN_FIELDS, looks_like_email, parse_import_content

router = APIRouter(prefix="/clients/import", tags=["Import clienti"])

PREVIEW_LIMIT = 10


def _parse(payload: schemas.ClientImportRequest):
    return parse_import_content(
        payload.format, payload.content,
        field_aliases=CLIENT_FIELD_ALIASES, known_fields=CLIENT_KNOWN_FIELDS,
        required_any=("name", "company"), required_fallback_field="name",
    )


@router.post("/preview", response_model=schemas.ClientImportPreviewOut)
def preview_import(payload: schemas.ClientImportRequest, user: models.User = Depends(get_current_user)):
    rows, errors = _parse(payload)
    preview_rows = [
        schemas.ClientImportRow(**{k: r.get(k) for k in CLIENT_KNOWN_FIELDS}, extra_fields=r.get("_extra") or None)
        for r in rows[:PREVIEW_LIMIT]
    ]
    return schemas.ClientImportPreviewOut(
        total_rows=len(rows) + len(errors), valid_rows=len(rows), errors=errors, preview=preview_rows,
    )


def _upsert_linked_contact(db: Session, tenant_id: str, client: "models.Client", extra_json: str):
    """Crea o aggiorna il contatto Rubrica collegato a questo cliente (Fase 9.6).
    Match nell'ordine: prima per client_id (il modo affidabile, se il contatto
    esiste già da un import precedente), poi per email valida come fallback
    (per non duplicare un contatto già presente in Rubrica con la stessa
    email ma senza ancora il collegamento client_id)."""
    contact = db.query(models.Contact).filter(
        models.Contact.tenant_id == tenant_id, models.Contact.client_id == client.id
    ).first()
    is_new = contact is None
    if contact is None and client.email and looks_like_email(client.email):
        contact = db.query(models.Contact).filter(
            models.Contact.tenant_id == tenant_id, models.Contact.email == client.email,
            models.Contact.client_id.is_(None),
        ).first()

    if contact is None:
        contact = models.Contact(id=models.gen_uuid(), tenant_id=tenant_id, category="cliente")
        db.add(contact)
        is_new = True

    contact.full_name = client.name
    contact.company = client.company
    contact.email = client.email
    contact.phone = client.phone
    contact.whatsapp = client.whatsapp
    contact.client_id = client.id
    if not contact.category:
        contact.category = "cliente"
    if extra_json:
        contact.extra_fields = extra_json
    return is_new


@router.post("/commit", response_model=schemas.ClientImportResultOut)
def commit_import(payload: schemas.ClientImportRequest, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    rows, errors = _parse(payload)

    created = 0
    updated = 0
    skipped = 0
    contacts_created = 0
    contacts_updated = 0

    for row in rows:
        extra = row.get("_extra") or None
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

        email = row.get("email")
        existing = None
        if email and looks_like_email(email):
            existing = db.query(models.Client).filter(
                models.Client.tenant_id == user.tenant_id, models.Client.email == email
            ).first()

        if existing:
            if payload.duplicate_strategy == "update":
                for field in ("name", "company", "phone", "whatsapp", "sector", "notes"):
                    if row.get(field):
                        setattr(existing, field, row[field])
                if extra_json:
                    existing.extra_fields = extra_json
                updated += 1
                client = existing
            else:
                skipped += 1
                continue
        else:
            client = models.Client(
                id=models.gen_uuid(),
                tenant_id=user.tenant_id,
                name=row.get("name"),
                company=row.get("company"),
                email=row.get("email"),
                phone=row.get("phone"),
                whatsapp=row.get("whatsapp"),
                sector=row.get("sector"),
                notes=row.get("notes"),
                extra_fields=extra_json,
            )
            db.add(client)
            created += 1

        if _upsert_linked_contact(db, user.tenant_id, client, extra_json):
            contacts_created += 1
        else:
            contacts_updated += 1

    db.commit()
    return schemas.ClientImportResultOut(
        created=created, updated=updated, skipped=skipped, errors=errors,
        contacts_created=contacts_created, contacts_updated=contacts_updated,
    )
