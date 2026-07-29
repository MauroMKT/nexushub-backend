"""Schemi Pydantic (request/response) per l'API Fase 1."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ---------- Auth / Onboarding (M11) ----------
class TenantRegister(BaseModel):
    account_type: str = "azienda"  # "azienda" | "persona_fisica"
    language: str = "it"

    # Comuni a entrambi i tipi di account
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

    # Solo per account_type == "azienda"
    company_type: Optional[str] = None  # spa | srl | srls | ditta_individuale | libero_professionista
    legal_name: Optional[str] = None  # ragione sociale
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
    phone: Optional[str] = None
    email: Optional[str] = None
    company_type: Optional[str] = None
    vat_number: Optional[str] = None
    vat_country_code: Optional[str] = None
    pec: Optional[str] = None
    contact_full_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

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
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    company_type: Optional[str] = None
    vat_number: Optional[str] = None
    pec: Optional[str] = None
    contact_full_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None


class UserProfileUpdate(BaseModel):
    """Modifica dei dati personali dell'utente loggato (non i dati del tenant)."""
    full_name: Optional[str] = None
    language: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


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
    created_at: datetime
    tags: List[TagOut] = []

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
    created_at: datetime

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


class ImpersonateOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_name: str
    impersonated_user_email: str


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
