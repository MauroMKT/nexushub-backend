"""Router Notifiche - centro notifiche in-app + preferenze canale (email/WhatsApp) per utente."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/notifications", tags=["Notifiche"])


@router.get("", response_model=List[schemas.NotificationOut])
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    q = db.query(models.Notification).filter(
        models.Notification.tenant_id == user.tenant_id, models.Notification.user_id == user.id
    )
    if unread_only:
        q = q.filter(models.Notification.is_read == False)  # noqa: E712
    return q.order_by(models.Notification.created_at.desc()).limit(100).all()


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    notif = db.query(models.Notification).filter(
        models.Notification.id == notification_id, models.Notification.user_id == user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notifica non trovata")
    notif.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.is_read == False  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.get("/preferences", response_model=schemas.UserOut)
def get_preferences(user: models.User = Depends(get_current_user)):
    return user


@router.put("/preferences", response_model=schemas.UserOut)
def update_preferences(payload: schemas.NotificationPreferencesUpdate, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
