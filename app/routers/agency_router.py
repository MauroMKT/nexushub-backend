"""Router del modulo pilota "Servizi IT & Marketing" (Fase 9.1): progetti
cliente con stato, eventuale retainer mensile e monte ore.

Pagina condivisa "Progetti Agenzia" (/agency-projects) tra due settori affini
(servizi_marketing e servizi_it): require_any_module lascia passare se ALMENO
uno dei due è attivo per il tenant, invece di richiederli entrambi."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_any_module

router = APIRouter(prefix="/agency/projects", tags=["Servizi IT & Marketing"])

_require = require_any_module("servizi_marketing", "servizi_it")


def _to_out(p: models.AgencyProject, client_name: Optional[str] = None) -> schemas.AgencyProjectOut:
    return schemas.AgencyProjectOut(
        id=p.id, title=p.title, client_id=p.client_id, client_name=client_name,
        status=p.status, is_retainer=p.is_retainer, retainer_monthly=p.retainer_monthly,
        hours_budget=p.hours_budget, hours_logged=p.hours_logged, notes=p.notes,
        created_at=p.created_at,
    )


@router.get("", response_model=List[schemas.AgencyProjectOut])
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    projects = db.query(models.AgencyProject).filter(
        models.AgencyProject.tenant_id == user.tenant_id
    ).order_by(models.AgencyProject.created_at.desc()).all()
    client_ids = {p.client_id for p in projects if p.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(p, clients.get(p.client_id)) for p in projects]


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
    return _to_out(project, client_name)


@router.patch("/{project_id}", response_model=schemas.AgencyProjectOut)
def update_project(project_id: str, payload: schemas.AgencyProjectUpdate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    project = db.query(models.AgencyProject).filter(
        models.AgencyProject.id == project_id, models.AgencyProject.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    client = db.query(models.Client).filter(models.Client.id == project.client_id).first() if project.client_id else None
    return _to_out(project, client.name if client else None)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    project = db.query(models.AgencyProject).filter(
        models.AgencyProject.id == project_id, models.AgencyProject.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    db.delete(project)
    db.commit()
    return {"ok": True}
