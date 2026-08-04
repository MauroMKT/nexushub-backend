"""Router generico per i moduli di settore SENZA una feature dedicata bespoke
(Fase 9.3, esteso in Fase 9.16). I moduli pilota (Servizi di Ingegneria, IT &
Marketing, Agenzie Immobiliari, Ristorazione & Hospitality, Palestre) hanno
ciascuno il proprio modello dati e il proprio router perché le loro esigenze
sono davvero diverse (fasi di commessa, prenotazioni tavoli, ecc.). I restanti
~17 settori del catalogo (studi legali, officine, e-commerce, ecc.) condividono
invece un'unica tabella (models.SectorRecord) parametrizzata da module_slug:
stessa struttura per tutti, ma l'etichetta mostrata in UI cambia per settore
tramite record_label_it/en definiti in modules_catalog.py. Fase 9.16 alza il
livello di dettaglio disponibile per tutti questi settori in un colpo solo:
priorità, scadenza, assegnatario, tag, campi personalizzati liberi (JSON) e
documenti allegati — così ogni settore generico ha una pagina di lavoro
realmente utile, senza dover costruire 17 schemi bespoke diversi."""
import base64
import binascii
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..modules_catalog import GENERIC_SECTOR_SLUGS

router = APIRouter(prefix="/sector-records", tags=["Moduli di settore (generico)"])

MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024


def _check_module_active(module_slug: str, db: Session, user: models.User) -> None:
    if module_slug not in GENERIC_SECTOR_SLUGS:
        raise HTTPException(status_code=404, detail="Modulo non gestito da questo endpoint")
    active = db.query(models.TenantModuleActivation).filter(
        models.TenantModuleActivation.tenant_id == user.tenant_id,
        models.TenantModuleActivation.module_id == module_slug,
    ).first()
    if not active:
        raise HTTPException(
            status_code=403,
            detail=f"Modulo '{module_slug}' non attivo per questa azienda. Attivalo da Moduli in Impostazioni.",
        )


def _decode_and_validate(content_base64: str, max_size: int) -> bytes:
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Contenuto file non valido (base64 non corretto)")
    if not raw:
        raise HTTPException(status_code=400, detail="Il file è vuoto")
    if len(raw) > max_size:
        raise HTTPException(status_code=400, detail=f"File troppo grande (max {max_size // (1024 * 1024)} MB)")
    return raw


def _custom_fields_to_json(fields: Optional[dict]) -> Optional[str]:
    if fields is None:
        return None
    return json.dumps(fields, ensure_ascii=False)


def _custom_fields_from_json(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _document_count(db: Session, record_id: str) -> int:
    return db.query(models.SectorRecordDocument).filter(
        models.SectorRecordDocument.record_id == record_id
    ).count()


def _get_record_or_404(module_slug: str, record_id: str, db: Session, user: models.User) -> models.SectorRecord:
    record = db.query(models.SectorRecord).filter(
        models.SectorRecord.id == record_id, models.SectorRecord.tenant_id == user.tenant_id,
        models.SectorRecord.module_slug == module_slug,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Elemento non trovato")
    return record


def _to_out(db: Session, r: models.SectorRecord, client_name: Optional[str] = None) -> schemas.SectorRecordOut:
    return schemas.SectorRecordOut(
        id=r.id, module_slug=r.module_slug, title=r.title,
        client_id=r.client_id, client_name=client_name,
        status=r.status.value if hasattr(r.status, "value") else r.status,
        value=r.value, reference_date=r.reference_date,
        priority=r.priority.value if hasattr(r.priority, "value") else (r.priority or "media"),
        due_date=r.due_date, assigned_to=r.assigned_to, tags=r.tags,
        custom_fields=_custom_fields_from_json(r.custom_fields),
        document_count=_document_count(db, r.id),
        notes=r.notes, created_at=r.created_at,
    )


@router.get("/{module_slug}", response_model=List[schemas.SectorRecordOut])
def list_records(module_slug: str, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    records = db.query(models.SectorRecord).filter(
        models.SectorRecord.tenant_id == user.tenant_id,
        models.SectorRecord.module_slug == module_slug,
    ).order_by(models.SectorRecord.created_at.desc()).all()
    client_ids = {r.client_id for r in records if r.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(db, r, clients.get(r.client_id)) for r in records]


@router.post("/{module_slug}", response_model=schemas.SectorRecordOut)
def create_record(module_slug: str, payload: schemas.SectorRecordCreate, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    client_name = None
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
        client_name = client.name
    try:
        status_val = models.SectorRecordStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Stato non valido")
    try:
        priority_val = models.SectorRecordPriority(payload.priority)
    except ValueError:
        raise HTTPException(status_code=400, detail="Priorità non valida")
    record = models.SectorRecord(
        tenant_id=user.tenant_id, module_slug=module_slug, client_id=payload.client_id,
        title=payload.title, status=status_val, value=payload.value,
        reference_date=payload.reference_date, priority=priority_val, due_date=payload.due_date,
        assigned_to=payload.assigned_to, tags=payload.tags,
        custom_fields=_custom_fields_to_json(payload.custom_fields), notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_out(db, record, client_name)


@router.patch("/{module_slug}/{record_id}", response_model=schemas.SectorRecordOut)
def update_record(module_slug: str, record_id: str, payload: schemas.SectorRecordUpdate,
                   db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    record = _get_record_or_404(module_slug, record_id, db, user)
    data = payload.dict(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        try:
            data["status"] = models.SectorRecordStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Stato non valido")
    if "priority" in data and data["priority"] is not None:
        try:
            data["priority"] = models.SectorRecordPriority(data["priority"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Priorità non valida")
    if "custom_fields" in data:
        data["custom_fields"] = _custom_fields_to_json(data["custom_fields"])
    for field, value in data.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    client = db.query(models.Client).filter(models.Client.id == record.client_id).first() if record.client_id else None
    return _to_out(db, record, client.name if client else None)


@router.delete("/{module_slug}/{record_id}")
def delete_record(module_slug: str, record_id: str, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    record = _get_record_or_404(module_slug, record_id, db, user)
    db.delete(record)
    db.commit()
    return {"ok": True}


# ---------- Documenti allegati (Fase 9.16) ----------
@router.get("/{module_slug}/{record_id}/documents", response_model=List[schemas.SectorRecordDocumentOut])
def list_documents(module_slug: str, record_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    _get_record_or_404(module_slug, record_id, db, user)
    return db.query(models.SectorRecordDocument).filter(
        models.SectorRecordDocument.record_id == record_id,
        models.SectorRecordDocument.tenant_id == user.tenant_id,
    ).order_by(models.SectorRecordDocument.created_at.desc()).all()


@router.post("/{module_slug}/{record_id}/documents", response_model=schemas.SectorRecordDocumentOut)
def upload_document(module_slug: str, record_id: str, payload: schemas.SectorRecordDocumentCreate,
                     db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    _get_record_or_404(module_slug, record_id, db, user)
    raw = _decode_and_validate(payload.content_base64, MAX_DOCUMENT_SIZE_BYTES)
    doc = models.SectorRecordDocument(
        tenant_id=user.tenant_id, record_id=record_id, filename=payload.filename,
        content_type=payload.content_type, size_bytes=len(raw), content_base64=payload.content_base64,
        uploaded_by_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{module_slug}/{record_id}/documents/{document_id}", response_model=schemas.SectorRecordDocumentContentOut)
def get_document(module_slug: str, record_id: str, document_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    _get_record_or_404(module_slug, record_id, db, user)
    doc = db.query(models.SectorRecordDocument).filter(
        models.SectorRecordDocument.id == document_id, models.SectorRecordDocument.record_id == record_id,
        models.SectorRecordDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return doc


@router.delete("/{module_slug}/{record_id}/documents/{document_id}")
def delete_document(module_slug: str, record_id: str, document_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    _get_record_or_404(module_slug, record_id, db, user)
    doc = db.query(models.SectorRecordDocument).filter(
        models.SectorRecordDocument.id == document_id, models.SectorRecordDocument.record_id == record_id,
        models.SectorRecordDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    db.delete(doc)
    db.commit()
    return {"ok": True}
