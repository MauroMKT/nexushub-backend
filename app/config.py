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
    # Lingue attive in Fase 1 (Sezione 6 del documento). Le altre 7 si aggiungono nelle fasi successive.
    supported_languages: list[str] = ["it", "en"]
    default_language: str = "it"


settings = Settings()
