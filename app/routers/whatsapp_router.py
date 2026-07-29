"""Router M6 - WhatsApp Business Hub."""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Business Hub"])


# --- Shared Inbox Messages ---
@router.get("/messages", response_model=List[schemas.WhatsAppMessageOut])
def list_messages(client_id: Optional[str] = None, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    q = db.query(models.WhatsAppMessage).filter(
        models.WhatsAppMessage.tenant_id == user.tenant_id
    )
    if client_id:
        q = q.filter(models.WhatsAppMessage.client_id == client_id)
    return q.order_by(models.WhatsAppMessage.created_at.asc()).all()


@router.post("/messages", response_model=schemas.WhatsAppMessageOut)
def send_message(payload: schemas.WhatsAppMessageCreate, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    # Verifica che il cliente esista
    client = db.query(models.Client).filter(
        models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
        
    # Crea il messaggio in uscita (outbound)
    msg = models.WhatsAppMessage(
        tenant_id=user.tenant_id,
        client_id=payload.client_id,
        direction="outbound",
        message_text=payload.message_text,
        status="sent",
        created_at=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    # Simula la consegna e la lettura dopo pochi secondi
    # (in un server reale verrebbe gestito asincronamente tramite webhook di consegna)
    msg.status = "read"
    db.commit()
    db.refresh(msg)
    
    # --- SIMULAZIONE BOT / RISPOSTA AUTOMATICA ---
    # Se il cliente scrive qualcosa di specifico, possiamo simulare una risposta inbound dopo 1 secondo.
    # In questo ambiente, aggiungiamo direttamente una risposta automatica mock se è una demo.
    if "ciao" in payload.message_text.lower():
        reply = models.WhatsAppMessage(
            tenant_id=user.tenant_id,
            client_id=payload.client_id,
            direction="inbound",
            message_text=f"Ciao! Sono l'assistente automatico di {user.tenant.name}. Come posso aiutarti oggi?",
            status="delivered",
            created_at=datetime.utcnow()
        )
        db.add(reply)
        db.commit()
        
    return msg


# --- Templates ---
@router.get("/templates", response_model=List[schemas.WhatsAppTemplateOut])
def list_templates(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.WhatsAppTemplate).filter(
        models.WhatsAppTemplate.tenant_id == user.tenant_id
    ).all()


@router.post("/templates", response_model=schemas.WhatsAppTemplateOut)
def create_template(payload: schemas.WhatsAppTemplateCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    tpl = models.WhatsAppTemplate(
        tenant_id=user.tenant_id,
        name=payload.name,
        content=payload.content,
        language=payload.language,
        is_approved=True,  # Approvato automaticamente per facilitare i test di sviluppo
        created_at=datetime.utcnow()
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/templates/{tpl_id}")
def delete_template(tpl_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tpl = db.query(models.WhatsAppTemplate).filter(
        models.WhatsAppTemplate.id == tpl_id, models.WhatsAppTemplate.tenant_id == user.tenant_id
    ).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template non trovato")
    db.delete(tpl)
    db.commit()
    return {"ok": True}


# --- Webhook Simulation ---
@router.post("/webhook-simulate")
def simulate_inbound_message(client_id: str, text: str, db: Session = Depends(get_db),
                             user: models.User = Depends(get_current_user)):
    """Simula la ricezione di un messaggio WhatsApp in entrata da parte di un cliente."""
    client = db.query(models.Client).filter(
        models.Client.id == client_id, models.Client.tenant_id == user.tenant_id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
        
    msg = models.WhatsAppMessage(
        tenant_id=user.tenant_id,
        client_id=client_id,
        direction="inbound",
        message_text=text,
        status="delivered",
        created_at=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
