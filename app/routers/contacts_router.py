"""Router Rubrica telefonica - contatti condivisi del team (clienti, fornitori, colleghi)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/contacts", tags=["Rubrica Telefonica"])


@router.get("", response_model=List[schemas.ContactOut])
def list_contacts(q: Optional[str] = None, category: Optional[str] = None,
                   db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = db.query(models.Contact).filter(models.Contact.tenant_id == user.tenant_id)
    if category:
        query = query.filter(models.Contact.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            models.Contact.full_name.ilike(like),
            models.Contact.company.ilike(like),
            models.Contact.phone.ilike(like),
            models.Contact.mobile.ilike(like),
            models.Contact.email.ilike(like),
        ))
    return query.order_by(models.Contact.full_name).all()


@router.post("", response_model=schemas.ContactOut)
def create_contact(payload: schemas.ContactCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    contact = models.Contact(tenant_id=user.tenant_id, **payload.dict())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _get_contact_or_404(contact_id: str, db: Session, user: models.User) -> models.Contact:
    contact = db.query(models.Contact).filter(
        models.Contact.id == contact_id, models.Contact.tenant_id == user.tenant_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contatto non trovato")
    return contact


@router.put("/{contact_id}", response_model=schemas.ContactOut)
def update_contact(contact_id: str, payload: schemas.ContactUpdate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    contact = _get_contact_or_404(contact_id, db, user)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}")
def delete_contact(contact_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    contact = _get_contact_or_404(contact_id, db, user)
    db.delete(contact)
    db.commit()
    return {"ok": True}


@router.post("/import-from-clients")
def import_from_clients(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Crea una voce in rubrica per ogni cliente CRM che non ha ancora un contatto collegato
    (comodo per popolare la rubrica al primo utilizzo)."""
    existing_client_ids = {
        c.client_id for c in db.query(models.Contact.client_id).filter(
            models.Contact.tenant_id == user.tenant_id, models.Contact.client_id.isnot(None)
        ).all()
    }
    clients = db.query(models.Client).filter(models.Client.tenant_id == user.tenant_id).all()
    created = 0
    for client in clients:
        if client.id in existing_client_ids:
            continue
        if not (client.phone or client.whatsapp or client.email):
            continue
        db.add(models.Contact(
            tenant_id=user.tenant_id, full_name=client.name, phone=client.phone,
            whatsapp=client.whatsapp, email=client.email, company=client.company,
            category="cliente", client_id=client.id,
        ))
        created += 1
    db.commit()
    return {"ok": True, "created": created}
