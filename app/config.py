"""
Configurazione centrale dell'applicazione NexusHub CRM.
Corrisponde ai "Requisiti tecnici" della Sezione 4 del documento di specifica
(Piano_di_Sviluppo.docx): architettura multi-tenant, autenticazione JWT.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "NexusHub CRM"
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./nexushub.db")
    # Lingue attive in Fase 1 & 2 (Sezione 6 del documento). Le altre si aggiungono nelle fasi successive.
    supported_languages: list[str] = ["it", "en", "fr", "es", "de", "zh", "ja", "ru", "ar"]
    default_language: str = "it"

    # --- Notifiche email reali (opzionale): se RESEND_API_KEY non è impostata,
    # le notifiche email restano solo "loggate" internamente senza invio reale. ---
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from_email: str = os.getenv("RESEND_FROM_EMAIL", "notifiche@nexushub.app")

    # --- Integrazione Google Calendar (opzionale): richiede un progetto OAuth
    # su Google Cloud Console. Finché queste variabili non sono impostate,
    # l'endpoint di stato risponde "configured": false. ---
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    # URL pubblico del frontend, usato per redirect post-OAuth e link nei messaggi.
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # --- Bootstrap del primo account super admin (platform_admin) ---
    # Va impostata una sola volta su Railway con un valore segreto a scelta di Mauro;
    # l'endpoint /platform-admin/bootstrap la richiede e funziona solo se non esiste
    # ancora nessun platform_admin, per evitare che chiunque possa auto-promuoversi.
    platform_admin_bootstrap_secret: str = os.getenv("PLATFORM_ADMIN_BOOTSTRAP_SECRET", "")

    # --- Abbonamenti reali (Stripe, opzionale) ---
    # Finché STRIPE_SECRET_KEY non è impostata, /billing/status risponde
    # "configured": false e checkout/portal restituiscono un errore chiaro
    # invece di fallire in modo oscuro (stesso pattern di Google Calendar).
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe_price_premium_monthly: str = os.getenv("STRIPE_PRICE_PREMIUM_MONTHLY", "")
    stripe_price_premium_annual: str = os.getenv("STRIPE_PRICE_PREMIUM_ANNUAL", "")
    stripe_price_enterprise_monthly: str = os.getenv("STRIPE_PRICE_ENTERPRISE_MONTHLY", "")
    stripe_price_enterprise_annual: str = os.getenv("STRIPE_PRICE_ENTERPRISE_ANNUAL", "")

    # --- Acquisto singolo di un modulo di settore (Fase 9.2) ---
    # Un solo price Stripe condiviso da tutti i moduli acquistabili singolarmente:
    # più semplice da configurare di 24 price distinti; se in futuro servissero
    # prezzi diversi per modulo si può sostituire con un dizionario slug -> price_id.
    stripe_price_module_addon: str = os.getenv("STRIPE_PRICE_MODULE_ADDON", "")


settings = Settings()
