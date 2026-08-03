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
    # Testo libero: le forme giuridiche societarie variano da paese a paese
    # (S.r.l., LLC, GmbH, SAS, ...), quindi non ha senso vincolarle a un enum
    # fisso pensato solo per l'Italia.
    company_type = Column(String, nullable=True)
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

    # --- Configurazione SMTP per l'invio reale delle campagne Email Marketing
    # (Fase 9.8). Ogni tenant usa il proprio server SMTP (self-service): non
    # c'è una chiave/API condivisa lato piattaforma, così "tutti gli account"
    # possono inviare email davvero senza dipendere da una quota centralizzata.
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_username = Column(String, nullable=True)
    smtp_password = Column(String, nullable=True)
    smtp_from_email = Column(String, nullable=True)
    smtp_from_name = Column(String, nullable=True)
    smtp_use_tls = Column(Boolean, default=True)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")

    @property
    def smtp_configured(self) -> bool:
        """True se il tenant ha impostato abbastanza per tentare un invio reale."""
        return bool(self.smtp_host and self.smtp_from_email)


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
    # Fase 9.5: colonne extra scoperte durante un import CSV/JSON/XML che non
    # corrispondono a nessun campo noto (name/company/email/...). Salvate come
    # JSON in un'unica colonna testo invece di alterare lo schema ad ogni CSV
    # diverso: così l'import "si adatta" al file senza perdere dati che non
    # avevano un campo dedicato.
    extra_fields = Column(Text, nullable=True)
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
    # Fase 9.8: l'invio non è più simulato (vedi email_router.py) — questi due
    # campi rendono visibile l'esito reale invece delle sole statistiche finte
    # di apertura/click che nessun invio SMTP diretto può davvero misurare.
    status = Column(String, default="draft")  # draft | sent | failed
    failed_count = Column(Integer, default=0)
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
    # Fase 9.5: vedi Client.extra_fields, stessa logica per l'import CSV in Rubrica.
    extra_fields = Column(Text, nullable=True)
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


# ---------- Moduli di settore attivabili (Fase 9) ----------
class TenantModuleActivation(Base):
    """Modulo di settore attivo per un tenant specifico. Il catalogo dei moduli
    disponibili è statico (vedi modules_catalog.py); questa tabella registra solo
    QUALI moduli sono accesi per QUALE tenant. module_id è lo slug stabile del
    modulo (es. "studi_medici"), non una foreign key verso una tabella catalogo,
    per restare coerente con l'approccio "catalogo in codice" del progetto."""
    __tablename__ = "tenant_module_activations"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    module_id = Column(String, nullable=False, index=True)
    activated_at = Column(DateTime, default=datetime.utcnow)
    # "admin" (autoattivazione entro il piano) | "platform_admin" (Super Admin) |
    # "auto_sector" (attivato in automatico alla registrazione in base al settore
    # dichiarato) | "purchased" (acquisto ricorrente del singolo modulo, Fase 9.2)
    activated_by = Column(String, default="admin")
    # Valorizzato solo se activated_by == "purchased": permette di risalire
    # all'abbonamento Stripe dedicato a questo modulo per gestirne la cancellazione.
    stripe_subscription_id = Column(String, nullable=True)


# ---------- Moduli pilota con funzionalità dedicata (Fase 9.1) ----------
class EngineeringProjectPhase(str, enum.Enum):
    progettazione = "progettazione"
    permessi = "permessi"
    esecuzione = "esecuzione"
    collaudo = "collaudo"
    chiuso = "chiuso"


class EngineeringProject(Base):
    """Commessa tecnica del modulo "Servizi di Ingegneria" (Fase 9.1)."""
    __tablename__ = "engineering_projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    title = Column(String, nullable=False)
    phase = Column(Enum(EngineeringProjectPhase), default=EngineeringProjectPhase.progettazione)
    deadline = Column(DateTime, nullable=True)
    budget = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client")


class AgencyProject(Base):
    """Progetto cliente del modulo "Servizi IT & Marketing" (Fase 9.1): milestone,
    stato ed eventuale retainer mensile e monte ore, per agenzie di marketing o IT."""
    __tablename__ = "agency_projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, default="in_corso")  # in_corso | in_pausa | completato
    is_retainer = Column(Boolean, default=False)
    retainer_monthly = Column(Float, nullable=True)
    hours_budget = Column(Float, nullable=True)
    hours_logged = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client")


class RealEstateProperty(Base):
    """Immobile in portafoglio del modulo "Agenzie Immobiliari" (Fase 9.1)."""
    __tablename__ = "real_estate_properties"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)  # proprietario o interessato
    title = Column(String, nullable=False)
    property_type = Column(String, default="residenziale")  # residenziale | commerciale | terreno | garage | altro
    address = Column(String, nullable=True)
    size_sqm = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    status = Column(String, default="disponibile")  # disponibile | in_trattativa | venduto | affittato
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client")


class Reservation(Base):
    """Prenotazione del modulo "Ristorazione & Hospitality" (Fase 9.1): tavolo per
    ristoranti/bar/locali, camera per hotel (table_label è testo libero apposta,
    per coprire entrambi i casi senza due tabelle separate)."""
    __tablename__ = "reservations"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    guest_name = Column(String, nullable=True)  # per ospiti non ancora presenti in anagrafica clienti
    party_size = Column(Integer, default=2)
    table_label = Column(String, nullable=True)  # es. "Tavolo 5" oppure "Camera 101"
    reservation_time = Column(DateTime, nullable=False)
    status = Column(String, default="confirmed")  # confirmed | seated | completed | cancelled | no_show
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client")


class MenuItem(Base):
    """Voce di menu del modulo "Ristorazione & Hospitality" (Fase 9.1)."""
    __tablename__ = "menu_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String, default="altro")  # antipasti | primi | secondi | dolci | bevande | altro
    price = Column(Float, default=0)
    description = Column(Text, nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------- Modulo pilota: Palestre e Centri Sportivi (Fase 9.9) ----------
# "palestre" nasceva come modulo "generico" (Fase 9.3, tabella SectorRecord
# condivisa). Le esigenze richieste (anagrafica socio completa, corsi con
# grado/cintura per le arti marziali, tessere, certificato medico con upload,
# foto socio, trofei per una classifica sociale) non entrano nello schema
# generico a campo singolo "title/status/value" — servono tabelle dedicate,
# come i 4 moduli pilota bespoke di Fase 9.1. Vedi gym_router.py e
# DEDICATED_ROUTES["palestre"] in modules_catalog.py.
class GymMember(Base):
    """Socio/atleta della palestra. client_id è opzionale: un socio può esistere
    anche senza essere (ancora) un Cliente CRM in senso commerciale."""
    __tablename__ = "gym_members"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)
    address = Column(String, nullable=False)
    fiscal_code = Column(String, nullable=True)  # codice fiscale, opzionale
    vat_number = Column(String, nullable=True)  # partita IVA, opzionale (es. personal trainer con P.IVA)
    card_number = Column(String, nullable=True)  # numero tessera del club
    federation_card_number = Column(String, nullable=True)  # numero tessera della federazione affiliata
    medical_certificate_ok = Column(Boolean, default=False)  # check rapido si/no, indipendente dal file caricato
    medical_certificate_expiry = Column(DateTime, nullable=True)
    photo_base64 = Column(Text, nullable=True)
    photo_content_type = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client")


class GymCourse(Base):
    """Corso offerto dalla palestra (es. "Karate", "Nuoto", "Pilates"). Catalogo
    estendibile dall'utente stesso al momento dell'iscrizione di un socio (vedi
    gym_router.py: create-if-missing per nome, case-insensitive), così il
    database dei corsi resta sempre completo senza un censimento preventivo."""
    __tablename__ = "gym_courses"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    is_martial_arts = Column(Boolean, default=False)  # abilita grado/cintura + anno nelle iscrizioni
    created_at = Column(DateTime, default=datetime.utcnow)


class GymEnrollment(Base):
    """Iscrizione di un socio a un corso. grade_name/grade_year hanno senso solo
    se il corso è di arti marziali (course.is_martial_arts), ma restano colonne
    libere qui invece che vincolate a un enum: gradi/cinture cambiano da
    disciplina a disciplina (cinture nel judo/karate, "dan"/"kyu", gradi nel
    ju-jitsu brasiliano, ecc.)."""
    __tablename__ = "gym_enrollments"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    member_id = Column(String, ForeignKey("gym_members.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("gym_courses.id"), nullable=False, index=True)
    grade_name = Column(String, nullable=True)  # es. "Cintura Nera 1° Dan"
    grade_year = Column(Integer, nullable=True)  # anno di decorrenza del grado
    enrolled_at = Column(DateTime, default=datetime.utcnow)

    member = relationship("GymMember")
    course = relationship("GymCourse")


class GymDocument(Base):
    """Documento legato a un socio: certificato medico (doc_type="medical_certificate",
    solo PDF o foto, vedi validazione in gym_router.py) o altro documento libero
    (doc_type="other"). Stesso pattern base64-in-DB di ClientDocument (Fase 8),
    per coerenza e perché il filesystem del container non è persistente su Railway."""
    __tablename__ = "gym_documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    member_id = Column(String, ForeignKey("gym_members.id"), nullable=False, index=True)
    doc_type = Column(String, default="other")  # medical_certificate | other
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_base64 = Column(Text, nullable=False)
    uploaded_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship("GymMember")


class GymTrophy(Base):
    """Trofeo/riconoscimento vinto da un socio in una gara o competizione, usato
    per calcolare la classifica sociale del club (vedi GET /gym/leaderboard)."""
    __tablename__ = "gym_trophies"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    member_id = Column(String, ForeignKey("gym_members.id"), nullable=False, index=True)
    title = Column(String, nullable=False)  # es. "Campionato Regionale Karate"
    placement = Column(String, nullable=True)  # es. "1° posto", "Oro"
    points = Column(Integer, default=0)  # peso opzionale per la classifica (0 = non pesato, si conta solo il numero)
    date_won = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship("GymMember")


# ---------- Moduli di settore "generici" (Fase 9.3) ----------
class SectorRecordStatus(str, enum.Enum):
    aperto = "aperto"
    in_corso = "in_corso"
    chiuso = "chiuso"


class SectorRecord(Base):
    """Elemento di lavoro generico per i settori del catalogo SENZA uno schema
    dati bespoke (a differenza dei 4 moduli pilota di Fase 9.1, che hanno
    ciascuno la propria tabella). Un'unica tabella parametrizzata da
    module_slug copre tutti gli altri ~18 settori (studi legali, officine,
    palestre, ecc.): l'etichetta mostrata in UI per "title" cambia per settore
    tramite record_label_it/en in modules_catalog.py, ma la struttura dati e
    gli endpoint (sector_records_router.py) restano condivisi."""
    __tablename__ = "sector_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    module_slug = Column(String, nullable=False, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    title = Column(String, nullable=False)
    status = Column(Enum(SectorRecordStatus), default=SectorRecordStatus.aperto)
    value = Column(Float, nullable=True)
    reference_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client")
