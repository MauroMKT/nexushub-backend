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
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    sector = Column(String, nullable=True)
    default_language = Column(String, default="it")
    plan = Column(String, default="free")  # free | starter | professional | enterprise
    primary_color = Column(String, default="#A9D6E5")
    logo_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
