"""Router Portale Clienti (M19) - accesso self-service separato per i clienti finali dei tenant.

Login e permessi sono completamente distinti da quelli del team interno (vedi
`get_current_portal_client` in `auth.py`): un cliente vede solo i propri
appuntamenti e task, mai i dati di altri clienti dello stesso tenant.
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_portal_client, verify_password
from ..automation_engine import run_automation
from ..database import get_db

router = APIRouter(prefix="/portal", tags=["Portale Clienti"])


@router.post("/login", response_model=schemas.PortalToken)
def portal_login(payload: schemas.PortalLoginRequest, db: Session = Depends(get_db)):
    portal_user = db.query(models.ClientPortalUser).filter(
        models.ClientPortalUser.email == payload.email, models.ClientPortalUser.is_active == True  # noqa: E712
    ).first()
    if not portal_user or not verify_password(payload.password, portal_user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o password non corrette")
    token = create_access_token(
        {"sub": portal_user.id, "client_id": portal_user.client_id, "tenant_id": portal_user.tenant_id, "portal": True}
    )
    return schemas.PortalToken(access_token=token)


@router.get("/me", response_model=schemas.PortalClientOut)
def portal_me(client: models.Client = Depends(get_current_portal_client)):
    return client


@router.get("/theme", response_model=schemas.PortalThemeOut)
def portal_theme(db: Session = Depends(get_db), client: models.Client = Depends(get_current_portal_client)):
    """Colori white-label del tenant del cliente autenticato, cosi' il portale rispecchia
    i colori scelti dall'azienda invece di mostrare sempre i colori di default (Fase 8)."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == client.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    return schemas.PortalThemeOut(
        primary_color=tenant.primary_color,
        secondary_color=tenant.secondary_color,
        accent_color=tenant.accent_color,
    )


@router.get("/appointments", response_model=List[schemas.AppointmentOut])
def portal_appointments(db: Session = Depends(get_db), client: models.Client = Depends(get_current_portal_client)):
    return db.query(models.Appointment).filter(
        models.Appointment.client_id == client.id
    ).order_by(models.Appointment.start_time).all()


@router.post("/appointments", response_model=schemas.AppointmentOut)
def portal_create_appointment(payload: schemas.PortalAppointmentCreate, db: Session = Depends(get_db),
                               client: models.Client = Depends(get_current_portal_client)):
    """Il cliente propone una riunione dal portale self-service: nasce sempre non
    confermata (status scheduled + is_public_booking=True); il team la conferma o
    la annulla con gli endpoint già esistenti in /appointments."""
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="L'orario di fine deve essere successivo a quello di inizio")
    if payload.start_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Scegli una data e un'ora nel futuro")

    appt = models.Appointment(
        tenant_id=client.tenant_id, client_id=client.id, owner_user_id=None,
        title=payload.title, location=payload.location,
        start_time=payload.start_time, end_time=payload.end_time,
        status=models.AppointmentStatus.scheduled, is_public_booking=True,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    run_automation(db, client.tenant_id, "appointment_created", {
        "appointment_id": appt.id, "client_id": client.id, "client_name": client.name, "owner_user_id": None,
    })
    return appt


@router.get("/tasks", response_model=List[schemas.TaskOut])
def portal_tasks(db: Session = Depends(get_db), client: models.Client = Depends(get_current_portal_client)):
    """Solo i task non ancora completati legati a questo cliente (vista essenziale, in sola lettura)."""
    return db.query(models.Task).filter(
        models.Task.client_id == client.id
    ).order_by(models.Task.due_date).all()
