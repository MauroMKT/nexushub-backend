"""Router del modulo pilota "Agenzie Immobiliari" (Fase 9.1): portafoglio
immobili con tipo, indirizzo, superficie, prezzo e stato (disponibile,
in trattativa, venduto, affittato), collegabile a un cliente (proprietario
o interessato) già in anagrafica."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_module

router = APIRouter(prefix="/real-estate/properties", tags=["Agenzie Immobiliari"])

_require = require_module("agenzie_immobiliari")


def _to_out(p: models.RealEstateProperty, client_name: Optional[str] = None) -> schemas.RealEstatePropertyOut:
    return schemas.RealEstatePropertyOut(
        id=p.id, title=p.title, client_id=p.client_id, client_name=client_name,
        property_type=p.property_type, address=p.address, size_sqm=p.size_sqm,
        price=p.price, status=p.status, notes=p.notes, created_at=p.created_at,
    )


@router.get("", response_model=List[schemas.RealEstatePropertyOut])
def list_properties(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    properties = db.query(models.RealEstateProperty).filter(
        models.RealEstateProperty.tenant_id == user.tenant_id
    ).order_by(models.RealEstateProperty.created_at.desc()).all()
    client_ids = {p.client_id for p in properties if p.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(p, clients.get(p.client_id)) for p in properties]


@router.post("", response_model=schemas.RealEstatePropertyOut)
def create_property(payload: schemas.RealEstatePropertyCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    client_name = None
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
        client_name = client.name
    prop = models.RealEstateProperty(
        tenant_id=user.tenant_id, client_id=payload.client_id, title=payload.title,
        property_type=payload.property_type, address=payload.address, size_sqm=payload.size_sqm,
        price=payload.price, status=payload.status, notes=payload.notes,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _to_out(prop, client_name)


@router.patch("/{property_id}", response_model=schemas.RealEstatePropertyOut)
def update_property(property_id: str, payload: schemas.RealEstatePropertyUpdate, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    prop = db.query(models.RealEstateProperty).filter(
        models.RealEstateProperty.id == property_id, models.RealEstateProperty.tenant_id == user.tenant_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Immobile non trovato")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(prop, field, value)
    db.commit()
    db.refresh(prop)
    client = db.query(models.Client).filter(models.Client.id == prop.client_id).first() if prop.client_id else None
    return _to_out(prop, client.name if client else None)


@router.delete("/{property_id}")
def delete_property(property_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    prop = db.query(models.RealEstateProperty).filter(
        models.RealEstateProperty.id == property_id, models.RealEstateProperty.tenant_id == user.tenant_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Immobile non trovato")
    db.delete(prop)
    db.commit()
    return {"ok": True}
