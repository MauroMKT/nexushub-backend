"""Router M8 - Email Marketing & Follow-up."""
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..email_sender import EmailSendError, send_email
from ..import_utils import looks_like_email

router = APIRouter(prefix="/email", tags=["Email Marketing"])


# --- Campaigns ---
@router.get("/campaigns", response_model=List[schemas.EmailCampaignOut])
def list_campaigns(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.EmailCampaign).filter(
        models.EmailCampaign.tenant_id == user.tenant_id
    ).all()


@router.post("/campaigns", response_model=schemas.EmailCampaignOut)
def create_campaign(payload: schemas.EmailCampaignCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    camp = models.EmailCampaign(
        tenant_id=user.tenant_id,
        title=payload.title,
        subject=payload.subject,
        body_html=payload.body_html,
        sent_count=0,
        open_count=0,
        click_count=0,
        created_at=datetime.utcnow()
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return camp


def _collect_recipient_emails(db: Session, tenant_id: str) -> List[str]:
    """Costruisce la lista destinatari di una campagna: unione di Clienti e
    Rubrica del tenant con un'email dall'aspetto valido, deduplicata
    (case-insensitive) — così un contatto già presente anche come cliente
    (vedi client_import_router._upsert_linked_contact) riceve una sola email."""
    emails = set()
    for row in db.query(models.Client.email).filter(models.Client.tenant_id == tenant_id).all():
        if row[0] and looks_like_email(row[0]):
            emails.add(row[0].strip().lower())
    for row in db.query(models.Contact.email).filter(models.Contact.tenant_id == tenant_id).all():
        if row[0] and looks_like_email(row[0]):
            emails.add(row[0].strip().lower())
    return sorted(emails)


@router.post("/campaigns/{camp_id}/send", response_model=schemas.EmailCampaignOut)
def send_campaign(camp_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    camp = db.query(models.EmailCampaign).filter(
        models.EmailCampaign.id == camp_id, models.EmailCampaign.tenant_id == user.tenant_id
    ).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campagna non trovata")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
    if not tenant or not tenant.smtp_configured:
        raise HTTPException(
            status_code=400,
            detail="Configura il tuo server SMTP in Impostazioni prima di inviare una campagna.",
        )

    recipients = _collect_recipient_emails(db, user.tenant_id)
    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="Nessun destinatario con email valida trovato tra Clienti e Rubrica.",
        )

    sent = failed = 0
    for to_email in recipients:
        try:
            send_email(tenant, to_email, camp.subject, camp.body_html)
            sent += 1
        except EmailSendError:
            failed += 1

    camp.sent_count = sent
    camp.failed_count = failed
    camp.open_count = 0
    camp.click_count = 0
    camp.status = "sent" if sent > 0 else "failed"

    db.commit()
    db.refresh(camp)
    return camp


# --- Sequences (Follow-up) ---
@router.get("/sequences", response_model=List[schemas.EmailSequenceOut])
def list_sequences(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.EmailSequence).filter(
        models.EmailSequence.tenant_id == user.tenant_id
    ).all()


@router.post("/sequences", response_model=schemas.EmailSequenceOut)
def create_sequence(payload: schemas.EmailSequenceCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    seq = models.EmailSequence(tenant_id=user.tenant_id, **payload.dict())
    db.add(seq)
    db.commit()
    db.refresh(seq)
    return seq


@router.put("/sequences/{seq_id}", response_model=schemas.EmailSequenceOut)
def update_sequence(seq_id: str, payload: schemas.EmailSequenceCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    seq = db.query(models.EmailSequence).filter(
        models.EmailSequence.id == seq_id, models.EmailSequence.tenant_id == user.tenant_id
    ).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequenza non trovata")
    for field, value in payload.dict().items():
        setattr(seq, field, value)
    db.commit()
    db.refresh(seq)
    return seq


@router.delete("/sequences/{seq_id}")
def delete_sequence(seq_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    seq = db.query(models.EmailSequence).filter(
        models.EmailSequence.id == seq_id, models.EmailSequence.tenant_id == user.tenant_id
    ).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequenza non trovata")
    db.delete(seq)
    db.commit()
    return {"ok": True}
