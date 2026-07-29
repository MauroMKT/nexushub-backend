"""Chat tra l'agenzia (team) e i suoi singoli clienti finali (Fase 7).

Un thread per cliente (client_id). Due gruppi di endpoint sullo stesso dato:
- lato team (sotto /clients/{client_id}/chat, auth normale, filtrato per tenant_id)
- lato portale clienti (sotto /portal/chat, auth separata del portale, M19)

MVP a polling, coerente con la chat interna team."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_portal_client, get_current_user
from ..database import get_db

team_router = APIRouter(prefix="/clients", tags=["Chat agenzia-clienti"])
portal_router = APIRouter(prefix="/portal", tags=["Chat agenzia-clienti"])


def _to_out(msg: models.ClientChatMessage, sender_name: str) -> schemas.ClientChatMessageOut:
    return schemas.ClientChatMessageOut(
        id=msg.id, client_id=msg.client_id, sender_type=msg.sender_type,
        sender_name=sender_name, body=msg.body, created_at=msg.created_at,
    )


# ---------- Lato team ----------
@team_router.get("/{client_id}/chat", response_model=List[schemas.ClientChatMessageOut])
def list_client_chat_team_side(client_id: str, after: Optional[str] = None, db: Session = Depends(get_db),
                                user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(models.Client.id == client_id, models.Client.tenant_id == user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    query = db.query(models.ClientChatMessage).filter(
        models.ClientChatMessage.client_id == client_id, models.ClientChatMessage.tenant_id == user.tenant_id
    )
    if after:
        after_msg = db.query(models.ClientChatMessage).filter(models.ClientChatMessage.id == after).first()
        if after_msg:
            query = query.filter(models.ClientChatMessage.created_at > after_msg.created_at)
    messages = query.order_by(models.ClientChatMessage.created_at.asc()).limit(200).all()

    sender_ids = {m.sender_user_id for m in messages if m.sender_user_id}
    senders = {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(sender_ids)).all()} if sender_ids else {}
    return [_to_out(m, senders.get(m.sender_user_id, client.name) if m.sender_type == "team" else client.name) for m in messages]


@team_router.post("/{client_id}/chat", response_model=schemas.ClientChatMessageOut)
def send_client_chat_team_side(client_id: str, payload: schemas.ClientChatMessageCreate, db: Session = Depends(get_db),
                                user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(models.Client.id == client_id, models.Client.tenant_id == user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto")

    msg = models.ClientChatMessage(
        tenant_id=user.tenant_id, client_id=client_id, sender_type="team",
        sender_user_id=user.id, body=payload.body.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _to_out(msg, user.full_name)


# ---------- Lato portale clienti ----------
@portal_router.get("/chat", response_model=List[schemas.ClientChatMessageOut])
def list_client_chat_portal_side(after: Optional[str] = None, db: Session = Depends(get_db),
                                  client: models.Client = Depends(get_current_portal_client)):
    query = db.query(models.ClientChatMessage).filter(models.ClientChatMessage.client_id == client.id)
    if after:
        after_msg = db.query(models.ClientChatMessage).filter(models.ClientChatMessage.id == after).first()
        if after_msg:
            query = query.filter(models.ClientChatMessage.created_at > after_msg.created_at)
    messages = query.order_by(models.ClientChatMessage.created_at.asc()).limit(200).all()

    sender_ids = {m.sender_user_id for m in messages if m.sender_user_id}
    senders = (
        {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(sender_ids)).all()}
        if sender_ids else {}
    )
    return [_to_out(m, senders.get(m.sender_user_id, "Team") if m.sender_type == "team" else client.name) for m in messages]


@portal_router.post("/chat", response_model=schemas.ClientChatMessageOut)
def send_client_chat_portal_side(payload: schemas.ClientChatMessageCreate, db: Session = Depends(get_db),
                                  client: models.Client = Depends(get_current_portal_client)):
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto")
    msg = models.ClientChatMessage(
        tenant_id=client.tenant_id, client_id=client.id, sender_type="client", body=payload.body.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _to_out(msg, client.name)
