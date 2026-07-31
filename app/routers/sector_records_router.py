"""Router generico per i moduli di settore SENZA una feature dedicata bespoke
(Fase 9.3). I 4 moduli pilota di Fase 9.1 (Servizi di Ingegneria, IT &
Marketing, Agenzie Immobiliari, Ristorazione & Hospitality) hanno ciascuno il
proprio modello dati e il proprio router perché le loro esigenze sono davvero
diverse (fasi di commessa, prenotazioni tavoli, ecc.). I restanti ~18 settori
del catalogo (studi legali, officine, palestre, e-commerce, ecc.) condividono
invece un'unica tabella (models.SectorRecord) parametrizzata da module_slug:
stessa struttura per tutti, ma l'etichetta mostrata in UI cambia per settore
tramite record_label_it/en definiti in modules_catalog.py. Così ogni settore
ha comunque una pagina reale e utile (non un semplice interruttore), senza
dover costruire 18 schemi bespoke diversi."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..modules_catalog import GENERIC_SECTOR_SLUGS

router = APIRouter(prefix="/sector-records", tags=["Moduli di settore (generico)"])


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


def _to_out(r: models.SectorRecord, client_name: Optional[str] = None) -> schemas.SectorRecordOut:
    return schemas.SectorRecordOut(
        id=r.id, module_slug=r.module_slug, title=r.title,
        client_id=r.client_id, client_name=client_name,
        status=r.status.value if hasattr(r.status, "value") else r.status,
        value=r.value, reference_date=r.reference_date, notes=r.notes,
        created_at=r.created_at,
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
    return [_to_out(r, clients.get(r.client_id)) for r in records]


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
    record = models.SectorRecord(
        tenant_id=user.tenant_id, module_slug=module_slug, client_id=payload.client_id,
        title=payload.title, status=status_val, value=payload.value,
        reference_date=payload.reference_date, notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_out(record, client_name)


@router.patch("/{module_slug}/{record_id}", response_model=schemas.SectorRecordOut)
def update_record(module_slug: str, record_id: str, payload: schemas.SectorRecordUpdate,
                   db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    record = db.query(models.SectorRecord).filter(
        models.SectorRecord.id == record_id, models.SectorRecord.tenant_id == user.tenant_id,
        models.SectorRecord.module_slug == module_slug,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Elemento non trovato")
    data = payload.dict(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        try:
            data["status"] = models.SectorRecordStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Stato non valido")
    for field, value in data.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    client = db.query(models.Client).filter(models.Client.id == record.client_id).first() if record.client_id else None
    return _to_out(record, client.name if client else None)


@router.delete("/{module_slug}/{record_id}")
def delete_record(module_slug: str, record_id: str, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    _check_module_active(module_slug, db, user)
    record = db.query(models.SectorRecord).filter(
        models.SectorRecord.id == record_id, models.SectorRecord.tenant_id == user.tenant_id,
        models.SectorRecord.module_slug == module_slug,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Elemento non trovato")
    db.delete(record)
    db.commit()
    return {"ok": True}
