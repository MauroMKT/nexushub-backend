"""
NexusHub CRM — Backend Fase 1 (MVP)
Implementa: M1 CRM Core, M2 Agenda & Calendario, M3 Reminder & Task,
M4 Gestione Appuntamenti, M11 Impostazioni/Team/Multilingua, Dashboard base.
Riferimento: Piano_di_Sviluppo.docx, Sezioni 3, 4 e 9 (Prompt Fase 1).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import (appointments_router, auth_router, clients_router,
                       dashboard_router, pipeline_router, tasks_router, team_router)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NexusHub CRM API",
    description="API Fase 1 (MVP) della piattaforma CRM modulare NexusHub.",
    version="0.1.0",
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


@app.get("/")
def root():
    return {"app": "NexusHub CRM", "status": "ok", "phase": "Fase 1 - MVP"}


@app.get("/health")
def health():
    return {"status": "healthy"}
