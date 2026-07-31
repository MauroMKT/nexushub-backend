"""Invio email reale via SMTP (Fase 9.8).

Prima di questa fase l'invio di una campagna (email_router.py) era interamente
simulato: nessuna email lasciava mai il server, venivano solo generate
statistiche casuali di apertura/click. Questo modulo sostituisce quella
simulazione con un invio SMTP vero, usando le credenziali che ogni tenant
configura autonomamente in Impostazioni (models.Tenant.smtp_*) — non c'è
nessuna chiave/API condivisa lato piattaforma, quindi la funzionalità è
disponibile "per tutti gli account" senza dipendere da una quota centralizzata
o da credenziali gestite da Mauro.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailSendError(Exception):
    """Sollevata quando l'invio di una singola email fallisce (SMTP non
    raggiungibile, credenziali errate, destinatario rifiutato, ecc.)."""


def send_email(tenant, to_email: str, subject: str, body_html: str) -> None:
    """Invia una singola email HTML usando la configurazione SMTP del tenant.
    Solleva EmailSendError se il tenant non ha configurato l'SMTP o se
    l'invio fallisce per qualsiasi motivo (rete, autenticazione, ecc.)."""
    if not tenant.smtp_configured:
        raise EmailSendError(
            "SMTP non configurato per questo account: vai in Impostazioni e "
            "inserisci i dati del tuo server SMTP prima di inviare."
        )

    from_name = (tenant.smtp_from_name or tenant.name or "").strip()
    from_header = f"{from_name} <{tenant.smtp_from_email}>" if from_name else tenant.smtp_from_email

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.attach(MIMEText(body_html or "", "html", "utf-8"))

    port = tenant.smtp_port or (587 if tenant.smtp_use_tls else 25)

    try:
        with smtplib.SMTP(tenant.smtp_host, port, timeout=20) as server:
            server.ehlo()
            if tenant.smtp_use_tls:
                server.starttls()
                server.ehlo()
            if tenant.smtp_username and tenant.smtp_password:
                server.login(tenant.smtp_username, tenant.smtp_password)
            server.sendmail(tenant.smtp_from_email, [to_email], msg.as_string())
    except Exception as exc:  # smtplib solleva diverse eccezioni specifiche: uniformiamo
        raise EmailSendError(str(exc)) from exc
