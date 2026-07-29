"""Chat interna del team, stile Slack (Fase 7).

MVP a polling: il frontend richiama GET /chat/channels/{id}/messages ogni
pochi secondi. Niente infrastruttura WebSocket dedicata, così funziona senza
modifiche al deploy Railway attuale. Ogni query filtra per tenant_id."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/chat", tags=["Chat interna team"])

DEFAULT_CHANNEL_NAME = "generale"


def _ensure_default_channel(db: Session, tenant_id: str) -> models.ChatChannel:
    channel = db.query(models.ChatChannel).filter(models.ChatChannel.tenant_id == tenant_id).first()
    if channel:
        return channel
    channel = models.ChatChannel(tenant_id=tenant_id, name=DEFAULT_CHANNEL_NAME)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/channels", response_model=List[schemas.ChatChannelOut])
def list_channels(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _ensure_default_channel(db, user.tenant_id)
    return (
        db.query(models.ChatChannel)
        .filter(models.ChatChannel.tenant_id == user.tenant_id)
        .order_by(models.ChatChannel.created_at.asc())
        .all()
    )


@router.post("/channels", response_model=schemas.ChatChannelOut)
def create_channel(payload: schemas.ChatChannelCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    channel = models.ChatChannel(tenant_id=user.tenant_id, name=payload.name)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def _to_message_out(msg: models.TeamChatMessage, sender_name: str) -> schemas.TeamChatMessageOut:
    return schemas.TeamChatMessageOut(
        id=msg.id, channel_id=msg.channel_id, sender_user_id=msg.sender_user_id,
        sender_name=sender_name, body=msg.body, created_at=msg.created_at,
    )


@router.get("/channels/{channel_id}/messages", response_model=List[schemas.TeamChatMessageOut])
def list_messages(channel_id: str, after: Optional[str] = None, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    channel = db.query(models.ChatChannel).filter(
        models.ChatChannel.id == channel_id, models.ChatChannel.tenant_id == user.tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canale non trovato")

    query = db.query(models.TeamChatMessage).filter(
        models.TeamChatMessage.channel_id == channel_id,
        models.TeamChatMessage.tenant_id == user.tenant_id,
    )
    if after:
        after_msg = db.query(models.TeamChatMessage).filter(models.TeamChatMessage.id == after).first()
        if after_msg:
            query = query.filter(models.TeamChatMessage.created_at > after_msg.created_at)
    messages = query.order_by(models.TeamChatMessage.created_at.asc()).limit(200).all()

    sender_ids = {m.sender_user_id for m in messages}
    senders = {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(sender_ids)).all()} if sender_ids else {}
    return [_to_message_out(m, senders.get(m.sender_user_id, "?")) for m in messages]


@router.post("/channels/{channel_id}/messages", response_model=schemas.TeamChatMessageOut)
def send_message(channel_id: str, payload: schemas.TeamChatMessageCreate, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    channel = db.query(models.ChatChannel).filter(
        models.ChatChannel.id == channel_id, models.ChatChannel.tenant_id == user.tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canale non trovato")
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto")

    msg = models.TeamChatMessage(
        tenant_id=user.tenant_id, channel_id=channel_id, sender_user_id=user.id, body=payload.body.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _to_message_out(msg, user.full_name)
