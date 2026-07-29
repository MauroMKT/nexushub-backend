"""
NexusHub CRM — Backend Fase 1 (MVP)
Implementa: M1 CRM Core, M2 Agenda & Calendario, M3 Reminder & Task,
M4 Gestione Appuntamenti, M11 Impostazioni/Team/Multilingua, Dashboard base.
Riferimento: Piano_di_Sviluppo.docx, Sezioni 3, 4 e 9 (Prompt Fase 1).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import Base, engine
from .routers import (appointments_router, auth_router, clients_router,
                       dashboard_router, pipeline_router, tasks_router, team_router,
                       automations_router, whatsapp_router, email_router,
                       contacts_router, notifications_router, client_portal_router,
                       google_calendar_router, platform_admin_router, billing_router,
                       chat_router, client_chat_router, client_documents_router,
                       client_import_router, accounting_router)

Base.metadata.create_all(bind=engine)

# Micro-migrazione: create_all crea solo le tabelle mancanti, non aggiunge colonne
# a tabelle già esistenti. Per colonne nuove aggiunte dopo il primo deploy (es.
# tenants.trade_name) le allineiamo qui con un ALTER TABLE idempotente, senza
# introdurre Alembic per un progetto di queste dimensioni.
_TENANT_COLUMN_MIGRATIONS = [
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS trade_name VARCHAR",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS zip_code VARCHAR",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS country VARCHAR",
]
for _stmt in _TENANT_COLUMN_MIGRATIONS:
    try:
        with engine.connect() as conn:
            conn.execute(text(_stmt))
            conn.commit()
    except Exception:
        pass  # dialetti che non supportano "IF NOT EXISTS" (es. SQLite in locale) vengono ignorati

app = FastAPI(
    title="NexusHub CRM API",
    description="API Fase 1 & 2 della piattaforma CRM modulare NexusHub.",
    version="0.2.0",
)

# In produzione limitare origins al dominio del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(clients_router.router)
app.include_router(pipeline_router.router)
app.include_router(appointments_router.router)
app.include_router(tasks_router.router)
app.include_router(team_router.router)
app.include_router(dashboard_router.router)
app.include_router(automations_router.router)
app.include_router(whatsapp_router.router)
app.include_router(email_router.router)
app.include_router(contacts_router.router)
app.include_router(notifications_router.router)
app.include_router(client_portal_router.router)
app.include_router(google_calendar_router.router)
app.include_router(platform_admin_router.router)
app.include_router(billing_router.router)
app.include_router(chat_router.router)
app.include_router(client_chat_router.team_router)
app.include_router(client_chat_router.portal_router)
app.include_router(client_documents_router.team_router)
app.include_router(client_documents_router.portal_router)
app.include_router(client_import_router.router)
app.include_router(accounting_router.router)


@app.get("/")
def root():
    return {"app": "NexusHub CRM", "status": "ok", "phase": "Fase 1 - MVP"}


@app.get("/health")
def health():
    return {"status": "healthy"}
