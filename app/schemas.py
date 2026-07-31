"""Schemi Pydantic (request/response) per l'API Fase 1."""
import json as _json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


def _parse_extra_fields(v):
    """extra_fields è salvato in DB come stringa JSON (Text); qui lo riportiamo
    a dict per l'output API. Usato dal validator di ClientOut/ContactOut."""
    if v is None or isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return _json.loads(v)
        except (TypeError, ValueError):
            return None
    return v


# ---------- Auth / Onboarding (M11) ----------
class TenantRegister(BaseModel):
    account_type: str = "azienda"  # "azienda" | "persona_fisica"
    language: str = "it"

    # Comuni a entrambi i tipi di account
    address: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

    # Solo per account_type == "azienda"
    company_type: Optional[str] = None  # spa | srl | srls | ditta_individuale | libero_professionista
    legal_name: Optional[str] = None  # ragione sociale
    trade_name: Optional[str] = None  # nome commerciale (se diverso dalla ragione sociale)
    sector: Optional[str] = None
    vat_number: Optional[str] = None
    pec: Optional[str] = None
    contact_full_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None

    # Solo per account_type == "persona_fisica"
    full_name: Optional[str] = None

    # Utente amministratore (sempre presente, per il login)
    admin_full_name: str
    admin_email: EmailStr
    admin_password: str


class VatCountryInfo(BaseModel):
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    is_italian: bool = False
    valid_format: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    language: str
    notify_email: bool = True
    notify_whatsapp: bool = False

    class Config:
        from_attributes = True


class NotificationPreferencesUpdate(BaseModel):
    notify_email: Optional[bool] = None
    notify_whatsapp: Optional[bool] = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "member"
    language: str = "it"


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    sector: Optional[str] = None
    default_language: str
    plan: str
    primary_color: str
    secondary_color: str
    accent_color: str
    account_type: str
    address: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company_type: Optional[str] = None
    trade_name: Optional[str] = None
    vat_number: Optional[str] = None
    vat_country_code: Optional[str] = None
    pec: Optional[str] = None
    contact_full_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    # Fase 9.8: configurazione SMTP per l'invio reale delle campagne email.
    # smtp_password NON è incluso qui apposta: non va mai restituito dalla API,
    # nemmeno al proprietario del tenant (si può solo sovrascrivere via TenantUpdate).
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: bool = True
    smtp_configured: bool = False

    class Config:
        from_attributes = True


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    default_language: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    sector: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    company_type: Optional[str] = None
    trade_name: Optional[str] = None
    vat_number: Optional[str] = None
    pec: Optional[str] = None
    contact_full_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    # Fase 9.8: impostazioni SMTP, modificabili dall'admin del tenant dalla
    # pagina Impostazioni. smtp_password è scrivibile ma mai leggibile (vedi TenantOut).
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[EmailStr] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: Optional[bool] = None


class UserProfileUpdate(BaseModel):
    """Modifica dei dati personali dell'utente loggato (non i dati del tenant)."""
    full_name: Optional[str] = None
    language: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class TenantSelfDelete(BaseModel):
    """Richiesta di cancellazione permanente e irreversibile del proprio account,
    da parte dell'amministratore del tenant. La password è richiesta come
    conferma per evitare cancellazioni accidentali o da sessioni compromesse."""
    password: str


# ---------- Clients / Tags / Deals (M1) ----------
class TagOut(BaseModel):
    id: str
    name: str
    color: str

    class Config:
        from_attributes = True


class ClientCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    sector: Optional[str] = None
    notes: Optional[str] = None
    currency: str = "EUR"
    tag_ids: List[str] = []


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    sector: Optional[str] = None
    notes: Optional[str] = None
    tag_ids: Optional[List[str]] = None


class ClientOut(BaseModel):
    id: str
    name: str
    company: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    whatsapp: Optional[str]
    sector: Optional[str]
    notes: Optional[str]
    currency: str
    # Fase 9.5: colonne extra da un import CSV/JSON/XML senza corrispondenza
    # nello schema fisso (vedi import_utils.py e Client.extra_fields).
    extra_fields: Optional[dict] = None
    created_at: datetime
    tags: List[TagOut] = []

    _validate_extra_fields = field_validator("extra_fields", mode="before")(_parse_extra_fields)

    class Config:
        from_attributes = True


class PipelineStageOut(BaseModel):
    id: str
    name: str
    order: int

    class Config:
        from_attributes = True


class DealCreate(BaseModel):
    client_id: str
    stage_id: str
    title: str
    value: float = 0
    currency: str = "EUR"


class DealMove(BaseModel):
    stage_id: str


class DealOut(BaseModel):
    id: str
    client_id: str
    stage_id: str
    title: str
    value: float
    currency: str

    class Config:
        from_attributes = True


# ---------- Appointments (M2 + M4) ----------
class AppointmentCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    is_public_booking: bool = False


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None


class AppointmentOut(BaseModel):
    id: str
    title: str
    client_id: Optional[str]
    location: Optional[str]
    start_time: datetime
    end_time: datetime
    status: str
    is_public_booking: bool = False

    class Config:
        from_attributes = True


# Richiesta di riunione self-service dal portale clienti (Fase 8): niente client_id
# né owner_user_id, valorizzati lato server dal token del portale. Nasce sempre con
# is_public_booking=True e status="scheduled": il team la conferma con l'endpoint
# /appointments/{id}/confirm già esistente lato team.
class PortalAppointmentCreate(BaseModel):
    title: str
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime


# ---------- Tasks (M3) ----------
class TaskCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    due_date: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[datetime] = None
    done: Optional[bool] = None


class TaskOut(BaseModel):
    id: str
    title: str
    client_id: Optional[str]
    due_date: Optional[datetime]
    done: bool
    is_recurring: bool

    class Config:
        from_attributes = True


# ---------- Dashboard ----------
class DashboardSummary(BaseModel):
    total_clients: int
    appointments_this_week: int
    tasks_due: int
    open_deals: int
    pipeline_value: float


# ---------- Automations & Blueprints (M5) ----------
class AutomationRuleCreate(BaseModel):
    name: str
    trigger_type: str
    conditions: str = "{}"
    actions: str = "[]"
    is_active: bool = True


class AutomationRuleOut(BaseModel):
    id: str
    name: str
    trigger_type: str
    conditions: str
    actions: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BlueprintCreate(BaseModel):
    name: str
    entity_type: str
    stages: str = "{}"
    is_active: bool = True


class BlueprintOut(BaseModel):
    id: str
    name: str
    entity_type: str
    stages: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- WhatsApp (M6) ----------
class WhatsAppMessageCreate(BaseModel):
    client_id: str
    direction: str  # "inbound" | "outbound"
    message_text: str
    status: str = "sent"


class WhatsAppMessageOut(BaseModel):
    id: str
    client_id: str
    direction: str
    message_text: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class WhatsAppTemplateCreate(BaseModel):
    name: str
    content: str
    language: str = "it"


class WhatsAppTemplateOut(BaseModel):
    id: str
    name: str
    content: str
    language: str
    is_approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Email Marketing (M8) ----------
class EmailCampaignCreate(BaseModel):
    title: str
    subject: str
    body_html: str


class EmailCampaignOut(BaseModel):
    id: str
    title: str
    subject: str
    body_html: str
    sent_count: int
    open_count: int
    click_count: int
    # Fase 9.8: esito reale dell'invio SMTP (vedi email_router.py), al posto
    # delle sole statistiche simulate open_count/click_count di prima.
    status: str = "draft"
    failed_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class EmailSequenceCreate(BaseModel):
    name: str
    trigger_stage_id: str
    steps: str = "[]"
    is_active: bool = True


class EmailSequenceOut(BaseModel):
    id: str
    name: str
    trigger_stage_id: str
    steps: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Rubrica telefonica (Contacts) ----------
class ContactCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    mobile: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    category: str = "altro"
    notes: Optional[str] = None
    client_id: Optional[str] = None


class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class ContactOut(BaseModel):
    id: str
    full_name: str
    phone: Optional[str]
    mobile: Optional[str]
    whatsapp: Optional[str]
    email: Optional[str]
    company: Optional[str]
    category: str
    notes: Optional[str]
    client_id: Optional[str]
    # Fase 9.5: vedi ClientOut.extra_fields, stessa logica per l'import Rubrica.
    extra_fields: Optional[dict] = None
    created_at: datetime

    _validate_extra_fields = field_validator("extra_fields", mode="before")(_parse_extra_fields)

    class Config:
        from_attributes = True


# ---------- Notifiche ----------
class NotificationOut(BaseModel):
    id: str
    channel: str
    title: str
    body: str
    related_type: Optional[str]
    related_id: Optional[str]
    delivery_status: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Portale clienti (M19) ----------
class PortalInviteRequest(BaseModel):
    email: EmailStr
    password: str


class PortalLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PortalToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PortalClientOut(BaseModel):
    id: str
    name: str
    company: Optional[str]
    email: Optional[str]

    class Config:
        from_attributes = True


class PortalThemeOut(BaseModel):
    """Colori white-label del tenant a cui appartiene il cliente autenticato (Fase 8:
    il portale clienti deve rispecchiare i colori scelti dall'azienda in Impostazioni,
    non i colori di default)."""
    primary_color: str
    secondary_color: str
    accent_color: str


# ---------- Integrazione Google Calendar ----------
class GoogleCalendarStatus(BaseModel):
    configured: bool
    connected: bool
    calendar_id: Optional[str] = None


# ---------- Super admin / platform_admin ----------
class PlatformAdminBootstrap(BaseModel):
    secret: str
    email: EmailStr
    full_name: str
    password: str


class PlatformAdminCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class PlatformTenantOut(BaseModel):
    id: str
    name: str
    slug: str
    account_type: str
    plan: str
    is_active: bool
    default_language: str
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_number: Optional[str] = None
    vat_country_code: Optional[str] = None
    created_at: datetime
    user_count: int = 0
    client_count: int = 0

    class Config:
        from_attributes = True


class PlatformTenantUpdate(BaseModel):
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None


class PlatformStats(BaseModel):
    total_tenants: int
    active_tenants: int
    suspended_tenants: int
    total_users: int
    total_clients: int
    tenants_by_plan: dict


# ---------- Abbonamenti (Fase 7) ----------
class BillingPlanOut(BaseModel):
    id: str
    name: str
    price_monthly: float
    price_annual: float
    max_users: Optional[int] = None
    max_clients: Optional[int] = None
    features: List[str] = []


class BillingStatus(BaseModel):
    configured: bool
    plan: str
    billing_cycle: Optional[str] = None
    subscription_status: Optional[str] = None
    stripe_connected: bool = False


class CheckoutRequest(BaseModel):
    plan: str
    billing_cycle: str


class CheckoutOut(BaseModel):
    checkout_url: str


class BillingPortalOut(BaseModel):
    portal_url: str


# ---------- Chat interna team (Fase 7) ----------
class ChatChannelCreate(BaseModel):
    name: str


class ChatChannelOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class TeamChatMessageCreate(BaseModel):
    body: str


class TeamChatMessageOut(BaseModel):
    id: str
    channel_id: str
    sender_user_id: str
    sender_name: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Chat agenzia-clienti (Fase 7) ----------
class ClientChatMessageCreate(BaseModel):
    body: str


class ClientChatMessageOut(BaseModel):
    id: str
    client_id: str
    sender_type: str
    sender_name: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Documenti nella scheda cliente (Fase 8) ---
class ClientDocumentCreate(BaseModel):
    filename: str
    content_type: str
    content_base64: str


class ClientDocumentOut(BaseModel):
    id: str
    client_id: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ClientDocumentContentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    content_base64: str


# --- Import clienti da CSV/JSON/XML (Fase 8) ---
class ClientImportRequest(BaseModel):
    format: str  # "csv" | "json" | "xml"
    content: str
    duplicate_strategy: str = "skip"  # "skip" | "update" (match per email, solo in fase di commit)


class ClientImportRow(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    sector: Optional[str] = None
    # Fase 9.6: Client.notes esiste in DB da sempre ma l'import non lo
    # popolava — vedi CLIENT_FIELD_ALIASES in import_utils.py.
    notes: Optional[str] = None
    # Fase 9.5: colonne del file senza corrispondenza nello schema fisso,
    # mostrate in anteprima così l'utente vede cosa verrà salvato in extra_fields.
    extra_fields: Optional[dict] = None


class ClientImportPreviewOut(BaseModel):
    total_rows: int
    valid_rows: int
    errors: List[str]
    preview: List[ClientImportRow]


class ClientImportResultOut(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]
    # Fase 9.6: ogni cliente creato/aggiornato da questo import genera o
    # aggiorna anche un contatto collegato in Rubrica (vedi
    # client_import_router.py) — questi due contatori lo rendono visibile
    # nel riepilogo invece di essere un effetto collaterale silenzioso.
    contacts_created: int = 0
    contacts_updated: int = 0


# --- Import Rubrica/Contatti da CSV/JSON/XML (Fase 9.5) ---
# Stessa forma dell'import Clienti sopra, campi diversi (vedi CONTACT_KNOWN_FIELDS
# in import_utils.py) perché Contact è un'anagrafica distinta da Client.
class ContactImportRequest(BaseModel):
    format: str  # "csv" | "json" | "xml"
    content: str
    duplicate_strategy: str = "skip"  # "skip" | "update" (match per email, solo in fase di commit)


class ContactImportRow(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    extra_fields: Optional[dict] = None


class ContactImportPreviewOut(BaseModel):
    total_rows: int
    valid_rows: int
    errors: List[str]
    preview: List[ContactImportRow]


class ContactImportResultOut(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]


# ---------- Gestionale contabilità (Fase 8, M20) ----------
class ChartOfAccountCreate(BaseModel):
    code: str
    name: str
    account_type: str  # asset | liability | equity | revenue | expense


class ChartOfAccountOut(BaseModel):
    id: str
    code: str
    name: str
    account_type: str
    is_system: bool

    class Config:
        from_attributes = True


class JournalLineCreate(BaseModel):
    account_id: str
    debit: float = 0
    credit: float = 0
    description: Optional[str] = None


class JournalLineOut(BaseModel):
    id: str
    account_id: str
    account_name: Optional[str] = None
    debit: float
    credit: float
    description: Optional[str] = None

    class Config:
        from_attributes = True


class JournalEntryCreate(BaseModel):
    entry_date: datetime
    description: str
    lines: List[JournalLineCreate]


class JournalEntryOut(BaseModel):
    id: str
    entry_date: datetime
    description: str
    source: str
    source_invoice_id: Optional[str] = None
    lines: List[JournalLineOut]

    class Config:
        from_attributes = True


class InvoiceLineCreate(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float = 0
    vat_rate: float = 22


class InvoiceLineOut(BaseModel):
    id: str
    description: str
    quantity: float
    unit_price: float
    vat_rate: float

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    client_id: str
    issue_date: datetime
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    lines: List[InvoiceLineCreate]


class InvoiceOut(BaseModel):
    id: str
    client_id: str
    client_name: Optional[str] = None
    number: Optional[str] = None
    issue_date: datetime
    due_date: Optional[datetime] = None
    status: str
    currency: str
    notes: Optional[str] = None
    subtotal: float
    vat_amount: float
    total: float
    paid_at: Optional[datetime] = None
    lines: List[InvoiceLineOut]

    class Config:
        from_attributes = True


class BalanceSheetSection(BaseModel):
    account_type: str
    accounts: List[dict]  # [{code, name, balance}]
    total: float


class BalanceSheetOut(BaseModel):
    as_of: datetime
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection
    balanced: bool  # assets == liabilities + equity


class IncomeStatementOut(BaseModel):
    start: datetime
    end: datetime
    revenue: BalanceSheetSection
    expenses: BalanceSheetSection
    net_income: float


# ---------- Moduli di settore attivabili (Fase 9) ----------
class ModuleCatalogItem(BaseModel):
    slug: str
    sector_group: str
    min_plan: str
    name_it: str
    name_en: str
    # Fase 9.4: nome del modulo nelle altre 7 lingue dell'app (prima mancavano,
    # e il frontend ricadeva sull'inglese per chi usava FR/DE/ES/ZH/JA/RU/AR).
    name_fr: Optional[str] = None
    name_de: Optional[str] = None
    name_es: Optional[str] = None
    name_zh: Optional[str] = None
    name_ja: Optional[str] = None
    name_ru: Optional[str] = None
    name_ar: Optional[str] = None
    is_active_for_tenant: bool = False
    unlocked: bool = True  # False se il piano del tenant non raggiunge min_plan
    has_dedicated_feature: bool = False  # True se ha una pagina propria (non solo etichetta)
    dedicated_route: Optional[str] = None  # rotta frontend della pagina dedicata, se presente
    purchased_standalone: bool = False  # True se attivo tramite acquisto singolo (Fase 9.2), non piano
    # Etichetta dell'elemento di lavoro per i moduli "generici" di Fase 9.3
    # (es. "Pratica Legale" per studi_legali): None per i 4 moduli pilota
    # bespoke di Fase 9.1, che hanno il proprio nome nella pagina dedicata.
    record_label_it: Optional[str] = None
    record_label_en: Optional[str] = None
    record_label_fr: Optional[str] = None
    record_label_de: Optional[str] = None
    record_label_es: Optional[str] = None
    record_label_zh: Optional[str] = None
    record_label_ja: Optional[str] = None
    record_label_ru: Optional[str] = None
    record_label_ar: Optional[str] = None
    # Fase 9.4: intestazione di gruppo (es. "Automotive") tradotta in tutte le
    # lingue, al posto del solo valore italiano grezzo di sector_group.
    sector_group_it: Optional[str] = None
    sector_group_en: Optional[str] = None
    sector_group_fr: Optional[str] = None
    sector_group_de: Optional[str] = None
    sector_group_es: Optional[str] = None
    sector_group_zh: Optional[str] = None
    sector_group_ja: Optional[str] = None
    sector_group_ru: Optional[str] = None
    sector_group_ar: Optional[str] = None


class TenantModuleActivationOut(BaseModel):
    module_id: str
    activated_at: datetime
    activated_by: str

    class Config:
        from_attributes = True


class ModulePublicCatalogItem(BaseModel):
    """Voce di catalogo minimale, senza dati legati a un tenant: usata dalla pagina
    di registrazione (non autenticata) per il menu a tendina "Settore"."""
    slug: str
    sector_group: str
    name_it: str
    name_en: str
    name_fr: Optional[str] = None
    name_de: Optional[str] = None
    name_es: Optional[str] = None
    name_zh: Optional[str] = None
    name_ja: Optional[str] = None
    name_ru: Optional[str] = None
    name_ar: Optional[str] = None
    record_label_it: Optional[str] = None
    record_label_en: Optional[str] = None
    record_label_fr: Optional[str] = None
    record_label_de: Optional[str] = None
    record_label_es: Optional[str] = None
    record_label_zh: Optional[str] = None
    record_label_ja: Optional[str] = None
    record_label_ru: Optional[str] = None
    record_label_ar: Optional[str] = None
    sector_group_it: Optional[str] = None
    sector_group_en: Optional[str] = None
    sector_group_fr: Optional[str] = None
    sector_group_de: Optional[str] = None
    sector_group_es: Optional[str] = None
    sector_group_zh: Optional[str] = None
    sector_group_ja: Optional[str] = None
    sector_group_ru: Optional[str] = None
    sector_group_ar: Optional[str] = None


# ---------- Moduli pilota con funzionalità dedicata (Fase 9.1) ----------
class EngineeringProjectCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
    phase: str = "progettazione"
    deadline: Optional[datetime] = None
    budget: float = 0
    notes: Optional[str] = None


class EngineeringProjectUpdate(BaseModel):
    title: Optional[str] = None
    client_id: Optional[str] = None
    phase: Optional[str] = None
    deadline: Optional[datetime] = None
    budget: Optional[float] = None
    notes: Optional[str] = None


class EngineeringProjectOut(BaseModel):
    id: str
    title: str
    client_id: Optional[str]
    client_name: Optional[str] = None
    phase: str
    deadline: Optional[datetime]
    budget: float
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AgencyProjectCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
    status: str = "in_corso"
    is_retainer: bool = False
    retainer_monthly: Optional[float] = None
    hours_budget: Optional[float] = None
    hours_logged: float = 0
    notes: Optional[str] = None


class AgencyProjectUpdate(BaseModel):
    title: Optional[str] = None
    client_id: Optional[str] = None
    status: Optional[str] = None
    is_retainer: Optional[bool] = None
    retainer_monthly: Optional[float] = None
    hours_budget: Optional[float] = None
    hours_logged: Optional[float] = None
    notes: Optional[str] = None


class AgencyProjectOut(BaseModel):
    id: str
    title: str
    client_id: Optional[str]
    client_name: Optional[str] = None
    status: str
    is_retainer: bool
    retainer_monthly: Optional[float]
    hours_budget: Optional[float]
    hours_logged: float
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RealEstatePropertyCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
    property_type: str = "residenziale"
    address: Optional[str] = None
    size_sqm: Optional[float] = None
    price: Optional[float] = None
    status: str = "disponibile"
    notes: Optional[str] = None


class RealEstatePropertyUpdate(BaseModel):
    title: Optional[str] = None
    client_id: Optional[str] = None
    property_type: Optional[str] = None
    address: Optional[str] = None
    size_sqm: Optional[float] = None
    price: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class RealEstatePropertyOut(BaseModel):
    id: str
    title: str
    client_id: Optional[str]
    client_name: Optional[str] = None
    property_type: str
    address: Optional[str]
    size_sqm: Optional[float]
    price: Optional[float]
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReservationCreate(BaseModel):
    client_id: Optional[str] = None
    guest_name: Optional[str] = None
    party_size: int = 2
    table_label: Optional[str] = None
    reservation_time: datetime
    status: str = "confirmed"
    notes: Optional[str] = None


class ReservationUpdate(BaseModel):
    client_id: Optional[str] = None
    guest_name: Optional[str] = None
    party_size: Optional[int] = None
    table_label: Optional[str] = None
    reservation_time: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ReservationOut(BaseModel):
    id: str
    client_id: Optional[str]
    client_name: Optional[str] = None
    guest_name: Optional[str]
    party_size: int
    table_label: Optional[str]
    reservation_time: datetime
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MenuItemCreate(BaseModel):
    name: str
    category: str = "altro"
    price: float = 0
    description: Optional[str] = None
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    is_available: Optional[bool] = None


class MenuItemOut(BaseModel):
    id: str
    name: str
    category: str
    price: float
    description: Optional[str]
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Moduli di settore "generici" (Fase 9.3) ----------
class SectorRecordCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
    status: str = "aperto"
    value: Optional[float] = None
    reference_date: Optional[datetime] = None
    notes: Optional[str] = None


class SectorRecordUpdate(BaseModel):
    title: Optional[str] = None
    client_id: Optional[str] = None
    status: Optional[str] = None
    value: Optional[float] = None
    reference_date: Optional[datetime] = None
    notes: Optional[str] = None


class SectorRecordOut(BaseModel):
    id: str
    module_slug: str
    title: str
    client_id: Optional[str]
    client_name: Optional[str] = None
    status: str
    value: Optional[float]
    reference_date: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
