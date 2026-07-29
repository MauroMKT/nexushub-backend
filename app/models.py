"""
Modelli dati Fase 1 (MVP) di NexusHub CRM.
Ogni tabella ha tenant_id per garantire l'isolamento multi-tenant richiesto
in Sezione 4.1 del documento di specifica.

Mappatura moduli -> tabelle:
  M1  CRM Core                -> Tenant, Client, Tag, ClientTag, Deal, PipelineStage
  M2  Agenda & Calendario     -> Appointment (event_type="calendar")
  M3  Reminder & Task         -> Task
  M4  Gestione Appuntamenti   -> Appointment (event_type="appointment")
  M11 Impostazioni/Team       -> Tenant, User
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Enum, Float, ForeignKey,
                         Integer, String, Table, Text)
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class RoleEnum(str, enum.Enum):
    admin = "admin"
    member = "member"
    platform_admin = "platform_admin"  # super admin: unica eccezione consapevole all'isolamento tenant_id


class AccountTypeEnum(str, enum.Enum):
    azienda = "azienda"
    persona_fisica = "persona_fisica"


class CompanyTypeEnum(str, enum.Enum):
    spa = "spa"  # Società per Azioni
    srl = "srl"  # Società a Responsabilità Limitata
    srls = "srls"  # Società a Responsabilità Limitata Semplificata
    ditta_individuale = "ditta_individuale"
    libero_professionista = "libero_professionista"


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    confirmed = "confirmed"
    cancelled = "cancelled"
    no_show = "no_show"
    completed = "completed"


client_tags = Table(
    "client_tags",
    Base.metadata,
    Column("client_id", String, ForeignKey("clients.id"), primary_key=True),
    Column("tag_id", String, ForeignKey("tags.id"), primary_key=True),
)


class Tenant(Base):
    """Azienda cliente (M11 - Impostazioni, Team & Multilingua)."""
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)  # ragione sociale (azienda) o nome e cognome (persona fisica)
    slug = Column(String, unique=True, index=True, nullable=False)
    sector = Column(String, nullable=True)
    default_language = Column(String, default="it")
    plan = Column(String, default="free")  # free | premium | enterprise
    primary_color = Column(String, default="#A9D6E5")
    secondary_color = Column(String, default="#B8E0C8")
    accent_color = Column(String, default="#F6C6C0")
    logo_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)  # sospeso dal super admin -> blocca l'accesso di tutto il tenant
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- Abbonamento / fatturazione (Stripe, opzionale) ---
    billing_cycle = Column(String, nullable=True)  # "monthly" | "annual"
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)  # active | trialing | past_due | canceled ...

    # --- Dati anagrafici di registrazione (comuni ad azienda e persona fisica) ---
    account_type = Column(Enum(AccountTypeEnum), default=AccountTypeEnum.azienda)
    address = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)  # CAP
    country = Column(String, nullable=True)  # nazione
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)

    # --- Solo per account_type == azienda ---
    company_type = Column(Enum(CompanyTypeEnum), nullable=True)
    trade_name = Column(String, nullable=True)  # nome commerciale (se diverso dalla ragione sociale)
    vat_number = Column(String, nullable=True)
    vat_country_code = Column(String, nullable=True)  # rilevato automaticamente dalla P.IVA
    pec = Column(String, nullable=True)  # solo aziende italiane
    contact_full_name = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

    # --- Numerazione sequenziale fatture (M20 - Gestionale Contabilità) ---
    invoice_seq_year = Column(Integer, nullable=True)
    invoice_seq_last = Column(Integer, default=0)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    """Utente/membro del team (M11)."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.member)
    language = Column(String, default="it")
    is_active = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=True)
    notify_whatsapp = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


class Tag(Base):
    """Tag di segmentazione clienti (M1)."""
    __tablename__ = "tags"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    color = Column(String, default="#B8E0C8")


class PipelineStage(Base):
    """Fase della pipeline vendite kanban (M1)."""
    __tablename__ = "pipeline_stages"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    order = Column(Integer, default=0)

    deals = relationship("Deal", back_populates="stage")


class Client(Base):
    """Anagrafica cliente/azienda (M1 - CRM Core)."""
    __tablename__ = "clients"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    company = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    currency = Column(String, default="EUR")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="clients")
    tags = relationship("Tag", secondary=client_tags, backref="clients")
    deals = relationship("Deal", back_populates="client", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="client", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="client")
    whatsapp_messages = relationship("WhatsAppMessage", back_populates="client", cascade="all, delete-orphan")


class Deal(Base):
    """Trattativa/opportunità nella pipeline kanban (M1)."""
    __tablename__ = "deals"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    stage_id = Column(String, ForeignKey("pipeline_stages.id"), nullable=False)
    title = Column(String, nullable=False)
    value = Column(Float, default=0)
    currency = Column(String, default="EUR")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="deals")
    stage = relationship("PipelineStage", back_populates="deals")


class Appointment(Base):
    """Evento di agenda / appuntamento cliente (M2 + M4)."""
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    title = Column(String, nullable=False)
    location = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.scheduled)
    is_public_booking = Column(Boolean, default=False)
    reminder_sent_24h = Column(Boolean, default=False)
    reminder_sent_1h = Column(Boolean, default=False)
    google_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="appointments")


class Task(Base):
    """Task / promemoria (M3 - Reminder & Task)."""
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    assigned_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    title = Column(String, nullable=False)
    due_date = Column(DateTime, nullable=True)
    done = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_rule = Column(String, nullable=True)  # es. "daily", "weekly", "monthly"
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="tasks")


class AutomationRule(Base):
    """Regola di automazione (M5)."""
    __tablename__ = "automation_rules"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False)  # es. "new_client", "stage_change", "task_due"
    conditions = Column(Text, default="{}")  # JSON string
    actions = Column(Text, default="[]")  # JSON string containing actions list
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Blueprint(Base):
    """Processo guidato con step e approvazioni (M5)."""
    __tablename__ = "blueprints"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)  # "client" o "deal"
    stages = Column(Text, default="{}")  # JSON configuration
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WhatsAppMessage(Base):
    """Messaggio WhatsApp inviato o ricevuto (M6)."""
    __tablename__ = "whatsapp_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False, index=True)
    direction = Column(String, nullable=False)  # "inbound" | "outbound"
    message_text = Column(Text, nullable=False)
    status = Column(String, default="sent")  # sent | delivered | read | failed
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="whatsapp_messages")


class WhatsAppTemplate(Base):
    """Template WhatsApp approvati (M6)."""
    __tablename__ = "whatsapp_templates"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String, default="it")
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailCampaign(Base):
    """Campagna Email Marketing (M8)."""
    __tablename__ = "email_campaigns"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body_html = Column(Text, nullable=False)
    sent_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailSequence(Base):
    """Sequenza di email di follow-up collegata alla pipeline (M8)."""
    __tablename__ = "email_sequences"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    trigger_stage_id = Column(String, ForeignKey("pipeline_stages.id"), nullable=False)
    steps = Column(Text, default="[]")  # JSON string of sequence steps e.g. [{"delay_days": 1, "subject": "Hi", "body": "..."}]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Contact(Base):
    """Rubrica telefonica condivisa del tenant (contatti generici, non solo clienti CRM)."""
    __tablename__ = "contacts"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    category = Column(String, default="altro")  # cliente | fornitore | collega | altro
    notes = Column(Text, nullable=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """Notifica interna/log di invio (email o WhatsApp) verso un membro del team (M11+)."""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String, default="in_app")  # in_app | email | whatsapp
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    related_type = Column(String, nullable=True)  # "appointment" | "task" | "deal" | "client"
    related_id = Column(String, nullable=True)
    delivery_status = Column(String, default="logged")  # logged | sent | failed | pending_provider
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClientPortalUser(Base):
    """Credenziali di accesso al portale self-service per un singolo cliente finale (M19)."""
    __tablename__ = "client_portal_users"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False, unique=True, index=True)
    email = Column(String, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client")


class ChatChannel(Base):
    """Canale di chat interna del team, stile Slack (Fase 7)."""
    __tablename__ = "chat_channels"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TeamChatMessage(Base):
    """Messaggio in un canale di chat interna del team (Fase 7)."""
    __tablename__ = "team_chat_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    channel_id = Column(String, ForeignKey("chat_channels.id"), nullable=False, index=True)
    sender_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClientChatMessage(Base):
    """Messaggio nel thread di chat tra l'agenzia e un singolo cliente (Fase 7)."""
    __tablename__ = "client_chat_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False, index=True)
    sender_type = Column(String, nullable=False)  # "team" | "client"
    sender_user_id = Column(String, ForeignKey("users.id"), nullable=True)  # valorizzato solo se sender_type == "team"
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClientDocument(Base):
    """Documento allegato alla scheda cliente (Fase 8). Il contenuto è salvato come
    base64 in DB (colonna Text) invece che su filesystem: evita di dipendere da uno
    storage persistente esterno, coerente con un deploy su piattaforme come Railway
    dove il filesystem del container non è garantito persistente tra i deploy."""
    __tablename__ = "client_documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False, index=True)
    uploaded_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_base64 = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GoogleCalendarConnection(Base):
    """Token OAuth Google Calendar collegati a un membro del team (M2 - integrazione esterna)."""
    __tablename__ = "google_calendar_connections"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    calendar_id = Column(String, default="primary")
    connected_at = Column(DateTime, default=datetime.utcnow)


# ---------- Gestionale contabilità (Fase 8, M20) ----------
class LedgerAccountType(str, enum.Enum):
    asset = "asset"          # attività (cassa, banca, crediti v/clienti...)
    liability = "liability"  # passività (debiti v/fornitori, IVA a debito...)
    equity = "equity"        # patrimonio netto (capitale sociale, utili...)
    revenue = "revenue"      # ricavi
    expense = "expense"      # costi


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class ChartOfAccount(Base):
    """Piano dei conti (contabilità in partita doppia). Un set base viene creato
    automaticamente per ogni tenant alla prima apertura del modulo contabilità."""
    __tablename__ = "chart_of_accounts"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    account_type = Column(Enum(LedgerAccountType), nullable=False)
    is_system = Column(Boolean, default=False)  # conti base creati automaticamente (non eliminabili)
    created_at = Column(DateTime, default=datetime.utcnow)


class JournalEntry(Base):
    """Registrazione di prima nota: un movimento di partita doppia, composto da
    almeno due righe (JournalLine) il cui totale dare deve sempre uguagliare
    il totale avere."""
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    entry_date = Column(DateTime, nullable=False)
    description = Column(String, nullable=False)
    source = Column(String, default="manual")  # "manual" | "invoice_issued" | "invoice_paid"
    source_invoice_id = Column(String, ForeignKey("invoices.id"), nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lines = relationship("JournalLine", back_populates="entry", cascade="all, delete-orphan")


class JournalLine(Base):
    """Singola riga dare/avere di una registrazione di prima nota."""
    __tablename__ = "journal_lines"

    id = Column(String, primary_key=True, default=gen_uuid)
    entry_id = Column(String, ForeignKey("journal_entries.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("chart_of_accounts.id"), nullable=False, index=True)
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    description = Column(String, nullable=True)

    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("ChartOfAccount")


class Invoice(Base):
    """Fattura emessa a un cliente (M20 - Gestionale Contabilità).
    Numerazione sequenziale per tenant e per anno (vedi Tenant.invoice_seq_year /
    invoice_seq_last). L'emissione (status != draft) e l'incasso (status == paid)
    generano automaticamente le relative registrazioni di prima nota."""
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False, index=True)
    number = Column(String, nullable=True)  # assegnato solo all'emissione (non ai draft)
    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.draft)
    currency = Column(String, default="EUR")
    notes = Column(Text, nullable=True)
    subtotal = Column(Float, default=0)
    vat_amount = Column(Float, default=0)
    total = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    client = relationship("Client")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLine(Base):
    """Riga di dettaglio di una fattura (descrizione, quantità, prezzo unitario, IVA)."""
    __tablename__ = "invoice_lines"

    id = Column(String, primary_key=True, default=gen_uuid)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False, index=True)
    description = Column(String, nullable=False)
    quantity = Column(Float, default=1)
    unit_price = Column(Float, default=0)
    vat_rate = Column(Float, default=22)  # percentuale, default aliquota IVA italiana ordinaria

    invoice = relationship("Invoice", back_populates="lines")
