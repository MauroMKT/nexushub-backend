"""Import clienti da CSV, JSON o XML (Fase 8, esteso Fase 9.5 con extra_fields).

Due step distinti, coerenti col resto dell'app (niente sorprese: l'utente vede
sempre un'anteprima prima di scrivere in DB):
- POST /clients/import/preview: parsing + validazione, nessuna scrittura.
- POST /clients/import/commit: stesso parsing, poi crea/aggiorna i Client.
  Il match dei duplicati è per email (dentro lo stesso tenant): se
  duplicate_strategy == "update" un cliente con la stessa email viene
  aggiornato, altrimenti la riga viene saltata.

Fase 9.5: le colonne del CSV/JSON/XML che non corrispondono a name/company/
email/phone/whatsapp/sector non vengono più scartate — finiscono in
Client.extra_fields (JSON) così il CRM "si adatta" a un file con colonne
diverse invece di perdere quei dati.
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..import_utils import CLIENT_FIELD_ALIASES, CLIENT_KNOWN_FIELDS, parse_import_content

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


@router.post("/commit", response_model=schemas.ClientImportResultOut)
def commit_import(payload: schemas.ClientImportRequest, db: Session = Depends(get_db),
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
        if email:
            existing = db.query(models.Client).filter(
                models.Client.tenant_id == user.tenant_id, models.Client.email == email
            ).first()

        if existing:
            if payload.duplicate_strategy == "update":
                for field in ("name", "company", "phone", "whatsapp", "sector"):
                    if row.get(field):
                        setattr(existing, field, row[field])
                if extra_json:
                    existing.extra_fields = extra_json
                updated += 1
            else:
                skipped += 1
            continue

        client = models.Client(
            tenant_id=user.tenant_id,
            name=row.get("name"),
            company=row.get("company"),
            email=row.get("email"),
            phone=row.get("phone"),
            whatsapp=row.get("whatsapp"),
            sector=row.get("sector"),
            extra_fields=extra_json,
        )
        db.add(client)
        created += 1

    db.commit()
    return schemas.ClientImportResultOut(created=created, updated=updated, skipped=skipped, errors=errors)
