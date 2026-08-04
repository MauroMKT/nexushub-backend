"""Router del modulo pilota "Servizi di Ingegneria" (Fase 9.1, esteso in Fase
9.16 con documenti/permessi, budget a consuntivo e storico cambi fase):
gestione delle commesse tecniche (progettazione, permessi, esecuzione,
collaudo) collegate opzionalmente a un cliente in anagrafica.

Ogni endpoint è protetto da require_module("servizi_ingegneria"): la pagina
dedicata resta invisibile/inutilizzabile se il tenant non ha questo modulo
attivo (attivato per settore alla registrazione, manualmente entro il piano,
dal Super Admin, o con acquisto singolo)."""
import base64
import binascii
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_module

router = APIRouter(prefix="/engineering/projects", tags=["Servizi di Ingegneria"])

_require = require_module("servizi_ingegneria")

MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024


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


def _document_count(db: Session, project_id: str) -> int:
    return db.query(models.EngineeringProjectDocument).filter(
        models.EngineeringProjectDocument.project_id == project_id
    ).count()


def _to_out(db: Session, p: models.EngineeringProject, client_name: Optional[str] = None) -> schemas.EngineeringProjectOut:
    budget_remaining = p.budget - (p.budget_actual or 0)
    return schemas.EngineeringProjectOut(
        id=p.id, title=p.title, client_id=p.client_id, client_name=client_name,
        phase=p.phase.value if hasattr(p.phase, "value") else p.phase,
        deadline=p.deadline, budget=p.budget, budget_actual=p.budget_actual or 0,
        budget_remaining=budget_remaining, over_budget=(p.budget_actual or 0) > p.budget,
        assigned_to=p.assigned_to, notes=p.notes, document_count=_document_count(db, p.id),
        created_at=p.created_at,
    )


def _get_project_or_404(project_id: str, db: Session, user: models.User) -> models.EngineeringProject:
    project = db.query(models.EngineeringProject).filter(
        models.EngineeringProject.id == project_id, models.EngineeringProject.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Commessa non trovata")
    return project


@router.get("", response_model=List[schemas.EngineeringProjectOut])
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    projects = db.query(models.EngineeringProject).filter(
        models.EngineeringProject.tenant_id == user.tenant_id
    ).order_by(models.EngineeringProject.created_at.desc()).all()
    client_ids = {p.client_id for p in projects if p.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(db, p, clients.get(p.client_id)) for p in projects]


@router.post("", response_model=schemas.EngineeringProjectOut)
def create_project(payload: schemas.EngineeringProjectCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    client_name = None
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
        client_name = client.name
    try:
        phase = models.EngineeringProjectPhase(payload.phase)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fase non valida")
    project = models.EngineeringProject(
        tenant_id=user.tenant_id, client_id=payload.client_id, title=payload.title,
        phase=phase, deadline=payload.deadline, budget=payload.budget,
        budget_actual=payload.budget_actual, assigned_to=payload.assigned_to, notes=payload.notes,
    )
    db.add(project)
    db.flush()
    db.add(models.EngineeringProjectPhaseLog(
        tenant_id=user.tenant_id, project_id=project.id, phase=phase.value,
    ))
    db.commit()
    db.refresh(project)
    return _to_out(db, project, client_name)


@router.patch("/{project_id}", response_model=schemas.EngineeringProjectOut)
def update_project(project_id: str, payload: schemas.EngineeringProjectUpdate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    project = _get_project_or_404(project_id, db, user)
    data = payload.dict(exclude_unset=True)
    phase_changed = False
    if "phase" in data and data["phase"] is not None:
        try:
            new_phase = models.EngineeringProjectPhase(data["phase"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Fase non valida")
        phase_changed = new_phase != project.phase
        data["phase"] = new_phase
    for field, value in data.items():
        setattr(project, field, value)
    if phase_changed:
        db.add(models.EngineeringProjectPhaseLog(
            tenant_id=user.tenant_id, project_id=project.id, phase=project.phase.value,
        ))
    db.commit()
    db.refresh(project)
    client = db.query(models.Client).filter(models.Client.id == project.client_id).first() if project.client_id else None
    return _to_out(db, project, client.name if client else None)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    project = _get_project_or_404(project_id, db, user)
    db.delete(project)
    db.commit()
    return {"ok": True}


# ---------- Storico fasi (Fase 9.16) ----------
@router.get("/{project_id}/phase-log", response_model=List[schemas.EngineeringProjectPhaseLogOut])
def list_phase_log(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    return db.query(models.EngineeringProjectPhaseLog).filter(
        models.EngineeringProjectPhaseLog.project_id == project_id,
        models.EngineeringProjectPhaseLog.tenant_id == user.tenant_id,
    ).order_by(models.EngineeringProjectPhaseLog.changed_at.asc()).all()


# ---------- Documenti / permessi (Fase 9.16) ----------
@router.get("/{project_id}/documents", response_model=List[schemas.EngineeringProjectDocumentOut])
def list_documents(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    return db.query(models.EngineeringProjectDocument).filter(
        models.EngineeringProjectDocument.project_id == project_id,
        models.EngineeringProjectDocument.tenant_id == user.tenant_id,
    ).order_by(models.EngineeringProjectDocument.created_at.desc()).all()


@router.post("/{project_id}/documents", response_model=schemas.EngineeringProjectDocumentOut)
def upload_document(project_id: str, payload: schemas.EngineeringProjectDocumentCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    raw = _decode_and_validate(payload.content_base64, MAX_DOCUMENT_SIZE_BYTES)
    doc = models.EngineeringProjectDocument(
        tenant_id=user.tenant_id, project_id=project_id, filename=payload.filename,
        content_type=payload.content_type, size_bytes=len(raw), content_base64=payload.content_base64,
        uploaded_by_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{project_id}/documents/{document_id}", response_model=schemas.EngineeringProjectDocumentContentOut)
def get_document(project_id: str, document_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    doc = db.query(models.EngineeringProjectDocument).filter(
        models.EngineeringProjectDocument.id == document_id, models.EngineeringProjectDocument.project_id == project_id,
        models.EngineeringProjectDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return doc


@router.delete("/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    doc = db.query(models.EngineeringProjectDocument).filter(
        models.EngineeringProjectDocument.id == document_id, models.EngineeringProjectDocument.project_id == project_id,
        models.EngineeringProjectDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    db.delete(doc)
    db.commit()
    return {"ok": True}
