"""
Sistema di notifiche interne (email/WhatsApp) verso i membri del team.

Ogni notifica viene sempre registrata come riga `Notification` (visibile in-app),
e in più:
  - se l'utente ha `notify_email=True` ed è configurata `RESEND_API_KEY`, viene
    inviata anche una vera email tramite l'API di Resend (https://resend.com);
    altrimenti resta solo "loggata" (delivery_status="logged").
  - se l'utente ha `notify_whatsapp=True`, la notifica viene marcata
    `delivery_status="pending_provider"`: l'invio reale via WhatsApp Business API
    richiede un provider approvato da Meta (non ancora collegato in questa fase,
    vedi CLAUDE.md "Cosa NON fare" sulle automazioni WhatsApp open-ended).

Questo modulo non solleva mai eccezioni verso il chiamante: un fallimento di
invio email non deve mai far fallire la richiesta HTTP che ha generato la notifica.
"""
import httpx
from sqlalchemy.orm import Session

from . import models
from .config import settings


def notify_user(
    db: Session,
    user: "models.User",
    title: str,
    body: str,
    related_type: str = None,
    related_id: str = None,
) -> "models.Notification":
    """Crea la notifica in-app e prova a recapitarla sui canali attivi dell'utente."""
    notif = models.Notification(
        tenant_id=user.tenant_id,
        user_id=user.id,
        channel="in_app",
        title=title,
        body=body,
        related_type=related_type,
        related_id=related_id,
        delivery_status="logged",
    )
    db.add(notif)
    db.flush()

    if user.notify_email:
        _try_send_email(user, title, body, notif)

    if user.notify_whatsapp:
        # Nessun provider WhatsApp Business collegato in questa fase: registriamo
        # l'intento senza inviare nulla, così il flusso è pronto quando verrà attivato.
        notif.delivery_status = "pending_provider" if notif.delivery_status == "logged" else notif.delivery_status

    db.commit()
    db.refresh(notif)
    return notif


def _try_send_email(user: "models.User", title: str, body: str, notif: "models.Notification") -> None:
    if not settings.resend_api_key:
        return  # Nessuna API key: resta "logged", nessun invio reale.
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from_email,
                "to": [user.email],
                "subject": title,
                "html": f"<p>{body}</p>",
            },
            timeout=10.0,
        )
        notif.delivery_status = "sent" if resp.status_code < 300 else "failed"
    except Exception:
        notif.delivery_status = "failed"


def notify_tenant_admins(db: Session, tenant_id: str, title: str, body: str,
                         related_type: str = None, related_id: str = None) -> None:
    """Notifica tutti gli admin del tenant (usato dal motore di automazioni)."""
    admins = db.query(models.User).filter(
        models.User.tenant_id == tenant_id, models.User.role == models.RoleEnum.admin
    ).all()
    for admin in admins:
        notify_user(db, admin, title, body, related_type, related_id)
