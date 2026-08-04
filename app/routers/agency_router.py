"""Router del modulo pilota "Servizi IT & Marketing" (Fase 9.1, esteso in Fase
9.16 con milestone, time tracking reale e documenti/deliverable): progetti
cliente con stato, eventuale retainer mensile e monte ore.

Pagina condivisa "Progetti Agenzia" (/agency-projects) tra due settori affini
(servizi_marketing e servizi_it): require_any_module lascia passare se ALMENO
uno dei due è attivo per il tenant, invece di richiederli entrambi.

Fase 9.16: hours_logged non è più un numero libero da modificare a mano, ma è
ricalcolato automaticamente come somma delle voci di time tracking (AgencyTimeEntry)
ogni volta che una voce viene aggiunta o rimossa — così il monte ore del
retainer riflette sempre il lavoro effettivamente registrato."""
import base64
import binascii
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_any_module

router = APIRouter(prefix="/agency/projects", tags=["Servizi IT & Marketing"])

_require = require_any_module("servizi_marketing", "servizi_it")

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


def _milestone_count(db: Session, project_id: str) -> int:
    return db.query(models.AgencyProjectMilestone).filter(
        models.AgencyProjectMilestone.project_id == project_id
    ).count()


def _document_count(db: Session, project_id: str) -> int:
    return db.query(models.AgencyProjectDocument).filter(
        models.AgencyProjectDocument.project_id == project_id
    ).count()


def _to_out(db: Session, p: models.AgencyProject, client_name: Optional[str] = None) -> schemas.AgencyProjectOut:
    hours_remaining = None
    over_budget = False
    if p.hours_budget is not None:
        hours_remaining = p.hours_budget - p.hours_logged
        over_budget = p.hours_logged > p.hours_budget
    return schemas.AgencyProjectOut(
        id=p.id, title=p.title, client_id=p.client_id, client_name=client_name,
        status=p.status, is_retainer=p.is_retainer, retainer_monthly=p.retainer_monthly,
        hours_budget=p.hours_budget, hours_logged=p.hours_logged, hours_remaining=hours_remaining,
        over_budget=over_budget, milestone_count=_milestone_count(db, p.id),
        document_count=_document_count(db, p.id), notes=p.notes, created_at=p.created_at,
    )


def _get_project_or_404(project_id: str, db: Session, user: models.User) -> models.AgencyProject:
    project = db.query(models.AgencyProject).filter(
        models.AgencyProject.id == project_id, models.AgencyProject.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return project


@router.get("", response_model=List[schemas.AgencyProjectOut])
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    projects = db.query(models.AgencyProject).filter(
        models.AgencyProject.tenant_id == user.tenant_id
    ).order_by(models.AgencyProject.created_at.desc()).all()
    client_ids = {p.client_id for p in projects if p.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(db, p, clients.get(p.client_id)) for p in projects]


@router.post("", response_model=schemas.AgencyProjectOut)
def create_project(payload: schemas.AgencyProjectCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    client_name = None
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
        client_name = client.name
    project = models.AgencyProject(
        tenant_id=user.tenant_id, client_id=payload.client_id, title=payload.title,
        status=payload.status, is_retainer=payload.is_retainer, retainer_monthly=payload.retainer_monthly,
        hours_budget=payload.hours_budget, hours_logged=payload.hours_logged, notes=payload.notes,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_out(db, project, client_name)


@router.patch("/{project_id}", response_model=schemas.AgencyProjectOut)
def update_project(project_id: str, payload: schemas.AgencyProjectUpdate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    project = _get_project_or_404(project_id, db, user)
    data = payload.dict(exclude_unset=True)
    # hours_logged è derivato dalle voci di time tracking dalla Fase 9.16: se il
    # chiamante prova comunque a impostarlo a mano lo ignoriamo silenziosamente,
    # per non rompere eventuali integrazioni esterne che inviano ancora il campo.
    data.pop("hours_logged", None)
    for field, value in data.items():
        setattr(project, field, value)
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


# ---------- Milestone (Fase 9.16) ----------
@router.get("/{project_id}/milestones", response_model=List[schemas.AgencyProjectMilestoneOut])
def list_milestones(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    return db.query(models.AgencyProjectMilestone).filter(
        models.AgencyProjectMilestone.project_id == project_id,
        models.AgencyProjectMilestone.tenant_id == user.tenant_id,
    ).order_by(models.AgencyProjectMilestone.due_date.asc()).all()


@router.post("/{project_id}/milestones", response_model=schemas.AgencyProjectMilestoneOut)
def create_milestone(project_id: str, payload: schemas.AgencyProjectMilestoneCreate, db: Session = Depends(get_db),
                      user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    milestone = models.AgencyProjectMilestone(
        tenant_id=user.tenant_id, project_id=project_id, title=payload.title,
        due_date=payload.due_date, status=payload.status, notes=payload.notes,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=schemas.AgencyProjectMilestoneOut)
def update_milestone(project_id: str, milestone_id: str, payload: schemas.AgencyProjectMilestoneUpdate,
                      db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    milestone = db.query(models.AgencyProjectMilestone).filter(
        models.AgencyProjectMilestone.id == milestone_id, models.AgencyProjectMilestone.project_id == project_id,
        models.AgencyProjectMilestone.tenant_id == user.tenant_id,
    ).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone non trovata")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(milestone, field, value)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.delete("/{project_id}/milestones/{milestone_id}")
def delete_milestone(project_id: str, milestone_id: str, db: Session = Depends(get_db),
                      user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    milestone = db.query(models.AgencyProjectMilestone).filter(
        models.AgencyProjectMilestone.id == milestone_id, models.AgencyProjectMilestone.project_id == project_id,
        models.AgencyProjectMilestone.tenant_id == user.tenant_id,
    ).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone non trovata")
    db.delete(milestone)
    db.commit()
    return {"ok": True}


# ---------- Time tracking (Fase 9.16) ----------
@router.get("/{project_id}/time-entries", response_model=List[schemas.AgencyTimeEntryOut])
def list_time_entries(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    return db.query(models.AgencyTimeEntry).filter(
        models.AgencyTimeEntry.project_id == project_id, models.AgencyTimeEntry.tenant_id == user.tenant_id,
    ).order_by(models.AgencyTimeEntry.entry_date.desc()).all()


@router.post("/{project_id}/time-entries", response_model=schemas.AgencyTimeEntryOut)
def create_time_entry(project_id: str, payload: schemas.AgencyTimeEntryCreate, db: Session = Depends(get_db),
                       user: models.User = Depends(_require)):
    project = _get_project_or_404(project_id, db, user)
    if payload.hours <= 0:
        raise HTTPException(status_code=400, detail="Le ore devono essere maggiori di zero")
    entry = models.AgencyTimeEntry(
        tenant_id=user.tenant_id, project_id=project_id, member_label=payload.member_label,
        hours=payload.hours, entry_date=payload.entry_date or datetime.utcnow(),
        description=payload.description,
    )
    db.add(entry)
    project.hours_logged = (project.hours_logged or 0) + payload.hours
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{project_id}/time-entries/{entry_id}")
def delete_time_entry(project_id: str, entry_id: str, db: Session = Depends(get_db),
                       user: models.User = Depends(_require)):
    project = _get_project_or_404(project_id, db, user)
    entry = db.query(models.AgencyTimeEntry).filter(
        models.AgencyTimeEntry.id == entry_id, models.AgencyTimeEntry.project_id == project_id,
        models.AgencyTimeEntry.tenant_id == user.tenant_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Voce di rendicontazione non trovata")
    project.hours_logged = max(0.0, (project.hours_logged or 0) - entry.hours)
    db.delete(entry)
    db.commit()
    return {"ok": True}


# ---------- Documenti / deliverable (Fase 9.16) ----------
@router.get("/{project_id}/documents", response_model=List[schemas.AgencyProjectDocumentOut])
def list_documents(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    return db.query(models.AgencyProjectDocument).filter(
        models.AgencyProjectDocument.project_id == project_id, models.AgencyProjectDocument.tenant_id == user.tenant_id,
    ).order_by(models.AgencyProjectDocument.created_at.desc()).all()


@router.post("/{project_id}/documents", response_model=schemas.AgencyProjectDocumentOut)
def upload_document(project_id: str, payload: schemas.AgencyProjectDocumentCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    raw = _decode_and_validate(payload.content_base64, MAX_DOCUMENT_SIZE_BYTES)
    doc = models.AgencyProjectDocument(
        tenant_id=user.tenant_id, project_id=project_id, filename=payload.filename,
        content_type=payload.content_type, size_bytes=len(raw), content_base64=payload.content_base64,
        uploaded_by_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{project_id}/documents/{document_id}", response_model=schemas.AgencyProjectDocumentContentOut)
def get_document(project_id: str, document_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    doc = db.query(models.AgencyProjectDocument).filter(
        models.AgencyProjectDocument.id == document_id, models.AgencyProjectDocument.project_id == project_id,
        models.AgencyProjectDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return doc


@router.delete("/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    _get_project_or_404(project_id, db, user)
    doc = db.query(models.AgencyProjectDocument).filter(
        models.AgencyProjectDocument.id == document_id, models.AgencyProjectDocument.project_id == project_id,
        models.AgencyProjectDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    db.delete(doc)
    db.commit()
    return {"ok": True}
