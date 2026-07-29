"""Router M2 (Agenda & Calendario) + M4 (Gestione Appuntamenti)."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..automation_engine import run_automation
from ..database import get_db

router = APIRouter(prefix="/appointments", tags=["Agenda & Appuntamenti"])


@router.get("", response_model=List[schemas.AppointmentOut])
def list_appointments(start: Optional[datetime] = None, end: Optional[datetime] = None,
                       db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Appointment).filter(models.Appointment.tenant_id == user.tenant_id)
    if start:
        q = q.filter(models.Appointment.start_time >= start)
    if end:
        q = q.filter(models.Appointment.end_time <= end)
    return q.order_by(models.Appointment.start_time).all()


@router.post("", response_model=schemas.AppointmentOut)
def create_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    appt = models.Appointment(
        tenant_id=user.tenant_id, owner_user_id=user.id, **payload.dict()
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    client = db.query(models.Client).filter(models.Client.id == appt.client_id).first() if appt.client_id else None
    run_automation(db, user.tenant_id, "appointment_created", {
        "appointment_id": appt.id, "client_id": appt.client_id,
        "client_name": client.name if client else "", "owner_user_id": user.id,
    })

    return appt


@router.put("/{appointment_id}", response_model=schemas.AppointmentOut)
def update_appointment(appointment_id: str, payload: schemas.AppointmentUpdate,
                        db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id, models.Appointment.tenant_id == user.tenant_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(appt, field, value)
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/confirm", response_model=schemas.AppointmentOut)
def confirm_appointment(appointment_id: str, db: Session = Depends(get_db),
                         user: models.User = Depends(get_current_user)):
    """Endpoint pubblico-simulato di conferma (in produzione va esposto senza JWT
    tramite link firmato, vedi M4 nel documento di specifica)."""
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id, models.Appointment.tenant_id == user.tenant_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    appt.status = models.AppointmentStatus.confirmed
    db.commit()
    db.refresh(appt)
    return appt


@router.delete("/{appointment_id}")
def delete_appointment(appointment_id: str, db: Session = Depends(get_db),
                        user: models.User = Depends(get_current_user)):
    appt = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id, models.Appointment.tenant_id == user.tenant_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    db.delete(appt)
    db.commit()
    return {"ok": True}
