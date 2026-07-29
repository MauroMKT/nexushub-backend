"""Import clienti da CSV, JSON o XML (Fase 8).

Due step distinti, coerenti col resto dell'app (niente sorprese: l'utente vede
sempre un'anteprima prima di scrivere in DB):
- POST /clients/import/preview: parsing + validazione, nessuna scrittura.
- POST /clients/import/commit: stesso parsing, poi crea/aggiorna i Client.
  Il match dei duplicati è per email (dentro lo stesso tenant): se
  duplicate_strategy == "update" un cliente con la stessa email viene
  aggiornato, altrimenti la riga viene saltata.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..import_utils import KNOWN_FIELDS, parse_import_content

router = APIRouter(prefix="/clients/import", tags=["Import clienti"])

PREVIEW_LIMIT = 10


@router.post("/preview", response_model=schemas.ClientImportPreviewOut)
def preview_import(payload: schemas.ClientImportRequest, user: models.User = Depends(get_current_user)):
    rows, errors = parse_import_content(payload.format, payload.content)
    preview_rows = [schemas.ClientImportRow(**{k: r.get(k) for k in KNOWN_FIELDS}) for r in rows[:PREVIEW_LIMIT]]
    return schemas.ClientImportPreviewOut(
        total_rows=len(rows) + len(errors), valid_rows=len(rows), errors=errors, preview=preview_rows,
    )


@router.post("/commit", response_model=schemas.ClientImportResultOut)
def commit_import(payload: schemas.ClientImportRequest, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    rows, errors = parse_import_content(payload.format, payload.content)

    created = 0
    updated = 0
    skipped = 0

    for row in rows:
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
        )
        db.add(client)
        created += 1

    db.commit()
    return schemas.ClientImportResultOut(created=created, updated=updated, skipped=skipped, errors=errors)
