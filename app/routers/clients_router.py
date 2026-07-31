"""Router M1 - CRM Core: anagrafica clienti, tag, storico."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, hash_password
from ..automation_engine import run_automation
from ..database import get_db

router = APIRouter(prefix="/clients", tags=["CRM Core - Clienti"])


# ---------- Da Rubrica a Cliente (Fase 9.8) ----------
@router.post("/from-contact/{contact_id}", response_model=schemas.ClientOut)
def create_client_from_contact(contact_id: str, db: Session = Depends(get_db),
                                user: models.User = Depends(get_current_user)):
    """Porta un nominativo dalla Rubrica ai Clienti: crea un nuovo Cliente a
    partire dai dati del Contatto e collega i due record (Contact.client_id),
    così il contatto compare da subito come "cliente" anche in Rubrica —
    stesso collegamento bidirezionale creato dall'import CSV (Fase 9.6), qui
    innescato manualmente dall'utente invece che da un file.
    Idempotente: se il contatto è già collegato a un cliente, restituisce
    quello esistente invece di crearne un duplicato."""
    contact = db.query(models.Contact).filter(
        models.Contact.id == contact_id, models.Contact.tenant_id == user.tenant_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contatto non trovato")

    if contact.client_id:
        existing = db.query(models.Client).filter(
            models.Client.id == contact.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if existing:
            return existing

    client = models.Client(
        tenant_id=user.tenant_id,
        name=contact.full_name,
        company=contact.company,
        email=contact.email,
        phone=contact.phone or contact.mobile,
        whatsapp=contact.whatsapp,
        notes=contact.notes,
        extra_fields=contact.extra_fields,
    )
    db.add(client)
    db.flush()  # serve client.id prima di collegarlo al contatto

    contact.client_id = client.id
    contact.category = "cliente"

    db.commit()
    db.refresh(client)

    run_automation(db, user.tenant_id, "new_client", {
        "client_id": client.id, "client_name": client.name, "owner_user_id": user.id,
    })

    return client


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

    run_automation(db, user.tenant_id, "new_client", {
        "client_id": client.id, "client_name": client.name, "owner_user_id": user.id,
    })

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


# ---------- Portale clienti (M19) - invito/gestione accesso da parte del team ----------
@router.post("/{client_id}/portal-invite")
def invite_client_to_portal(client_id: str, payload: schemas.PortalInviteRequest,
                             db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Crea (o resetta la password di) un accesso al portale self-service per questo cliente.
    Il cliente potrà poi accedere da /portal/login con l'email e la password qui impostate."""
    client = _get_client_or_404(client_id, db, user)

    existing = db.query(models.ClientPortalUser).filter(
        models.ClientPortalUser.client_id == client.id
    ).first()
    if existing:
        existing.email = payload.email
        existing.hashed_password = hash_password(payload.password)
        existing.is_active = True
        db.commit()
        return {"ok": True, "status": "updated"}

    portal_user = models.ClientPortalUser(
        tenant_id=user.tenant_id,
        client_id=client.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(portal_user)
    db.commit()
    return {"ok": True, "status": "created"}


@router.delete("/{client_id}/portal-invite")
def revoke_client_portal_access(client_id: str, db: Session = Depends(get_db),
                                 user: models.User = Depends(get_current_user)):
    client = _get_client_or_404(client_id, db, user)
    portal_user = db.query(models.ClientPortalUser).filter(
        models.ClientPortalUser.client_id == client.id
    ).first()
    if portal_user:
        db.delete(portal_user)
        db.commit()
    return {"ok": True}
