"""
Router Integrazione Google Calendar (M2 - estensione esterna).

Richiede un progetto OAuth su Google Cloud Console (Client ID + Client Secret +
Redirect URI autorizzato) fornito come variabili d'ambiente GOOGLE_CLIENT_ID /
GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI. Finché queste non sono impostate,
`/integrations/google-calendar/status` risponde `configured: false` e gli altri
endpoint restituiscono 400 con un messaggio esplicativo, invece di fallire in modo
oscuro: è la stessa logica di "attivazione differita" usata per l'invio email reale.
"""
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/integrations/google-calendar", tags=["Integrazione Google Calendar"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)


@router.get("/status", response_model=schemas.GoogleCalendarStatus)
def status(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    conn = db.query(models.GoogleCalendarConnection).filter(
        models.GoogleCalendarConnection.user_id == user.id
    ).first()
    return schemas.GoogleCalendarStatus(
        configured=_is_configured(),
        connected=conn is not None,
        calendar_id=conn.calendar_id if conn else None,
    )


@router.get("/auth-url")
def auth_url(user: models.User = Depends(get_current_user)):
    if not _is_configured():
        raise HTTPException(
            status_code=400,
            detail="Google Calendar non configurato: serve creare un progetto OAuth su Google Cloud Console "
                   "e impostare GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI sul backend.",
        )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": user.id,
    }
    return {"auth_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    """Redirect target configurato su Google Cloud Console. `state` contiene lo user_id
    (impostato in /auth-url) per sapere a quale membro del team collegare i token."""
    if not _is_configured():
        raise HTTPException(status_code=400, detail="Google Calendar non configurato")

    user = db.query(models.User).filter(models.User.id == state).first()
    if not user:
        raise HTTPException(status_code=400, detail="Utente non valido per questo collegamento")

    resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=10.0)
    if resp.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"Scambio token Google fallito: {resp.text[:200]}")

    data = resp.json()
    expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))

    conn = db.query(models.GoogleCalendarConnection).filter(
        models.GoogleCalendarConnection.user_id == user.id
    ).first()
    if not conn:
        conn = models.GoogleCalendarConnection(tenant_id=user.tenant_id, user_id=user.id, access_token="")
        db.add(conn)

    conn.access_token = data["access_token"]
    if data.get("refresh_token"):
        conn.refresh_token = data["refresh_token"]
    conn.token_expiry = expiry
    db.commit()

    return {"ok": True, "redirect": f"{settings.frontend_url}/settings?google_calendar=connected"}


@router.delete("")
def disconnect(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    conn = db.query(models.GoogleCalendarConnection).filter(
        models.GoogleCalendarConnection.user_id == user.id
    ).first()
    if conn:
        db.delete(conn)
        db.commit()
    return {"ok": True}


@router.post("/sync")
def sync_appointments(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Invia (crea/aggiorna) su Google Calendar gli appuntamenti dei prossimi 30 giorni
    di proprietà dell'utente collegato. Sincronizzazione monodirezionale CRM -> Google."""
    conn = db.query(models.GoogleCalendarConnection).filter(
        models.GoogleCalendarConnection.user_id == user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=400, detail="Nessun account Google Calendar collegato per questo utente")

    now = datetime.utcnow()
    appointments = db.query(models.Appointment).filter(
        models.Appointment.tenant_id == user.tenant_id,
        models.Appointment.owner_user_id == user.id,
        models.Appointment.start_time >= now,
        models.Appointment.start_time <= now + timedelta(days=30),
    ).all()

    headers = {"Authorization": f"Bearer {conn.access_token}"}
    events_url = GOOGLE_CALENDAR_EVENTS_URL.format(calendar_id=conn.calendar_id)
    synced, failed = 0, 0

    for appt in appointments:
        body = {
            "summary": appt.title,
            "location": appt.location or "",
            "start": {"dateTime": appt.start_time.isoformat() + "Z"},
            "end": {"dateTime": appt.end_time.isoformat() + "Z"},
        }
        try:
            if appt.google_event_id:
                resp = httpx.put(f"{events_url}/{appt.google_event_id}", headers=headers, json=body, timeout=10.0)
            else:
                resp = httpx.post(events_url, headers=headers, json=body, timeout=10.0)
                if resp.status_code < 300:
                    appt.google_event_id = resp.json().get("id")
            if resp.status_code < 300:
                synced += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    db.commit()
    return {"ok": True, "synced": synced, "failed": failed, "total": len(appointments)}
