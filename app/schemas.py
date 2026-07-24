"""Schemi Pydantic (request/response) per l'API Fase 1."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ---------- Auth / Onboarding (M11) ----------
class TenantRegister(BaseModel):
    company_name: str
    sector: Optional[str] = None
    admin_full_name: str
    admin_email: EmailStr
    admin_password: str
    language: str = "it"


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    default_language: Optional[str] = None
    primary_color: Optional[str] = None


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

    class Config:
        from_attributes = True


# ---------- Tasks (M3) ----------
class TaskCreate(BaseModel):
    title: str
    client_id: Optional[str] = None
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
