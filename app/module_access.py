"""Dipendenza condivisa per proteggere le rotte dei moduli pilota di settore
(Fase 9.1: engineering_router, agency_router, realestate_router, hospitality_router).

Ogni pagina dedicata (es. "Commesse Tecniche" del modulo Servizi di Ingegneria)
deve restare visibile/utilizzabile SOLO se il tenant ha quel modulo attivo in
tenant_module_activations - a prescindere da come sia stato attivato (piano,
Super Admin, autoattivazione per settore, o acquisto singolo). Non importa qui
la logica di piano (già applicata a monte in modules_router.py quando il modulo
viene attivato): questa dipendenza controlla solo lo stato "attivo/non attivo"."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_user
from .database import get_db


def require_module(module_slug: str):
    """Restituisce una dipendenza FastAPI che blocca l'accesso con 403 se il
    modulo `module_slug` non è attivo per il tenant dell'utente corrente."""

    def _dependency(
        db: Session = Depends(get_db),
        user: models.User = Depends(get_current_user),
    ) -> models.User:
        active = db.query(models.TenantModuleActivation).filter(
            models.TenantModuleActivation.tenant_id == user.tenant_id,
            models.TenantModuleActivation.module_id == module_slug,
        ).first()
        if not active:
            raise HTTPException(
                status_code=403,
                detail=f"Modulo '{module_slug}' non attivo per questa azienda. Attivalo da Moduli in Impostazioni.",
            )
        return user

    return _dependency


def require_any_module(*module_slugs: str):
    """Come require_module, ma per pagine condivise da più settori affini (es.
    "Progetti Agenzia" usato sia da servizi_marketing che da servizi_it, oppure
    "Hospitality" condiviso da ristorazione/bar/locali notturni/hotel): basta
    che UNO dei moduli elencati sia attivo per il tenant."""

    def _dependency(
        db: Session = Depends(get_db),
        user: models.User = Depends(get_current_user),
    ) -> models.User:
        active = db.query(models.TenantModuleActivation).filter(
            models.TenantModuleActivation.tenant_id == user.tenant_id,
            models.TenantModuleActivation.module_id.in_(module_slugs),
        ).first()
        if not active:
            raise HTTPException(
                status_code=403,
                detail=f"Nessuno dei moduli richiesti è attivo per questa azienda. Attivane uno da Moduli in Impostazioni.",
            )
        return user

    return _dependency
