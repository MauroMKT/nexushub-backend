"""Router M1 - CRM Core: anagrafica clienti, tag, storico."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/clients", tags=["CRM Core - Clienti"])


@router.get("", response_model=List[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Client).filter(models.Client.tenant_id == user.tenant_id).all()


@router.post("", response_model=schemas.ClientOut)
def create_client(payload: schemas.ClientCreate, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    client = models.Client(
        tenant_id=user.tenant_id,
        name=payload.name, company=payload.company, email=payload.email,
        phone=payload.phone, whatsapp=payload.whatsapp, sector=payload.sector,
        notes=payload.notes, currency=payload.currency,
    )
    if payload.tag_ids:
        client.tags = db.query(models.Tag).filter(
            models.Tag.id.in_(payload.tag_ids), models.Tag.tenant_id == user.tenant_id
        ).all()
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _get_client_or_404(client_id: str, db: Session, user: models.User) -> models.Client:
    client = db.query(models.Client).filter(
        models.Client.id == client_id, models.Client.tenant_id == user.tenant_id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return client


@router.get("/{client_id}", response_model=schemas.ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _get_client_or_404(client_id, db, user)


@router.put("/{client_id}", response_model=schemas.ClientOut)
def update_client(client_id: str, payload: schemas.ClientUpdate, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    client = _get_client_or_404(client_id, db, user)
    for field, value in payload.dict(exclude_unset=True, exclude={"tag_ids"}).items():
        setattr(client, field, value)
    if payload.tag_ids is not None:
        client.tags = db.query(models.Tag).filter(
            models.Tag.id.in_(payload.tag_ids), models.Tag.tenant_id == user.tenant_id
        ).all()
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}")
def delete_client(client_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    client = _get_client_or_404(client_id, db, user)
    db.delete(client)
    db.commit()
    return {"ok": True}


# ---------- Tag ----------
@router.get("/tags/all", response_model=List[schemas.TagOut])
def list_tags(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Tag).filter(models.Tag.tenant_id == user.tenant_id).all()


@router.post("/tags", response_model=schemas.TagOut)
def create_tag(name: str, color: str = "#B8E0C8", db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    tag = models.Tag(tenant_id=user.tenant_id, name=name, color=color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
