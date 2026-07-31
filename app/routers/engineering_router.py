"""Router del modulo pilota "Servizi di Ingegneria" (Fase 9.1): gestione delle
commesse tecniche (progettazione, permessi, esecuzione, collaudo) collegate
opzionalmente a un cliente in anagrafica.

Ogni endpoint è protetto da require_module("servizi_ingegneria"): la pagina
dedicata resta invisibile/inutilizzabile se il tenant non ha questo modulo
attivo (attivato per settore alla registrazione, manualmente entro il piano,
dal Super Admin, o con acquisto singolo)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_module

router = APIRouter(prefix="/engineering/projects", tags=["Servizi di Ingegneria"])

_require = require_module("servizi_ingegneria")


def _to_out(p: models.EngineeringProject, client_name: Optional[str] = None) -> schemas.EngineeringProjectOut:
    return schemas.EngineeringProjectOut(
        id=p.id, title=p.title, client_id=p.client_id, client_name=client_name,
        phase=p.phase.value if hasattr(p.phase, "value") else p.phase,
        deadline=p.deadline, budget=p.budget, notes=p.notes, created_at=p.created_at,
    )


@router.get("", response_model=List[schemas.EngineeringProjectOut])
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    projects = db.query(models.EngineeringProject).filter(
        models.EngineeringProject.tenant_id == user.tenant_id
    ).order_by(models.EngineeringProject.created_at.desc()).all()
    client_ids = {p.client_id for p in projects if p.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(p, clients.get(p.client_id)) for p in projects]


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
        phase=phase, deadline=payload.deadline, budget=payload.budget, notes=payload.notes,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_out(project, client_name)


@router.patch("/{project_id}", response_model=schemas.EngineeringProjectOut)
def update_project(project_id: str, payload: schemas.EngineeringProjectUpdate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    project = db.query(models.EngineeringProject).filter(
        models.EngineeringProject.id == project_id, models.EngineeringProject.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Commessa non trovata")
    data = payload.dict(exclude_unset=True)
    if "phase" in data and data["phase"] is not None:
        try:
            data["phase"] = models.EngineeringProjectPhase(data["phase"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Fase non valida")
    for field, value in data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    client = db.query(models.Client).filter(models.Client.id == project.client_id).first() if project.client_id else None
    return _to_out(project, client.name if client else None)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    project = db.query(models.EngineeringProject).filter(
        models.EngineeringProject.id == project_id, models.EngineeringProject.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Commessa non trovata")
    db.delete(project)
    db.commit()
    return {"ok": True}
