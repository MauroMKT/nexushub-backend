"""Import Rubrica (Contatti) da CSV, JSON o XML (Fase 9.5).

Mirror di client_import_router.py: la Rubrica finora poteva solo "importare"
i clienti già presenti nel CRM (POST /contacts/import-from-clients, vedi
contacts_router.py) — non c'era un vero import da file. Stesso pattern in due
step (preview → commit, mai scrittura diretta) e stessa logica di
extra_fields per le colonne del file che non corrispondono a un campo noto
della Rubrica (full_name/phone/mobile/whatsapp/email/company/category/notes).

Il match dei duplicati è per email (dentro lo stesso tenant), come per i
Clienti: se duplicate_strategy == "update" un contatto con la stessa email
viene aggiornato, altrimenti la riga viene saltata. Contact.full_name è
NOT NULL in DB: se il file non ha una colonna "nome" ma ha company o email,
la usiamo come nome (stesso fallback usato per Client.name/company).
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..import_utils import CONTACT_FIELD_ALIASES, CONTACT_KNOWN_FIELDS, looks_like_email, parse_import_content

router = APIRouter(prefix="/contacts/import", tags=["Import Rubrica"])

PREVIEW_LIMIT = 10


def _parse(payload: schemas.ContactImportRequest):
    return parse_import_content(
        payload.format, payload.content,
        field_aliases=CONTACT_FIELD_ALIASES, known_fields=CONTACT_KNOWN_FIELDS,
        required_any=("full_name", "company", "email"), required_fallback_field="full_name",
    )


@router.post("/preview", response_model=schemas.ContactImportPreviewOut)
def preview_import(payload: schemas.ContactImportRequest, user: models.User = Depends(get_current_user)):
    rows, errors = _parse(payload)
    preview_rows = [
        schemas.ContactImportRow(**{k: r.get(k) for k in CONTACT_KNOWN_FIELDS}, extra_fields=r.get("_extra") or None)
        for r in rows[:PREVIEW_LIMIT]
    ]
    return schemas.ContactImportPreviewOut(
        total_rows=len(rows) + len(errors), valid_rows=len(rows), errors=errors, preview=preview_rows,
    )


@router.post("/commit", response_model=schemas.ContactImportResultOut)
def commit_import(payload: schemas.ContactImportRequest, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    rows, errors = _parse(payload)

    created = 0
    updated = 0
    skipped = 0

    for row in rows:
        extra = row.get("_extra") or None
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

        existing = None
        email = row.get("email")
        if email and looks_like_email(email):
            existing = db.query(models.Contact).filter(
                models.Contact.tenant_id == user.tenant_id, models.Contact.email == email
            ).first()

        if existing:
            if payload.duplicate_strategy == "update":
                for field in ("full_name", "phone", "mobile", "whatsapp", "company", "category", "notes"):
                    if row.get(field):
                        setattr(existing, field, row[field])
                if extra_json:
                    existing.extra_fields = extra_json
                updated += 1
            else:
                skipped += 1
            continue

        contact = models.Contact(
            tenant_id=user.tenant_id,
            full_name=row.get("full_name"),
            phone=row.get("phone"),
            mobile=row.get("mobile"),
            whatsapp=row.get("whatsapp"),
            email=row.get("email"),
            company=row.get("company"),
            category=row.get("category") or "altro",
            notes=row.get("notes"),
            extra_fields=extra_json,
        )
        db.add(contact)
        created += 1

    db.commit()
    return schemas.ContactImportResultOut(created=created, updated=updated, skipped=skipped, errors=errors)
