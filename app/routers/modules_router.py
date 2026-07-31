"""Router dei moduli di settore attivabili (Fase 9).

Il catalogo dei moduli (quali esistono, in che settore, con che piano minimo)
è statico e vive in modules_catalog.py. QUALI moduli sono attivi per QUALE
tenant è invece dati vivi in models.TenantModuleActivation.

Un amministratore di tenant può autoattivare/disattivare un modulo solo se il
piano del proprio tenant raggiunge il piano minimo richiesto (min_plan); in
caso contrario riceve un 402 con l'indicazione del piano necessario, per
guidarlo verso l'upgrade in Impostazioni > Abbonamento. Il super admin bypassa
sempre questo limite tramite gli endpoint dedicati in platform_admin_router.py."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..modules_catalog import MODULE_BY_SLUG, MODULE_CATALOG, plan_meets_minimum

router = APIRouter(prefix="/modules", tags=["Moduli di settore"])


def _catalog_for_tenant(db: Session, tenant: models.Tenant) -> List[schemas.ModuleCatalogItem]:
    active_slugs = {
        row.module_id
        for row in db.query(models.TenantModuleActivation.module_id)
        .filter(models.TenantModuleActivation.tenant_id == tenant.id)
        .all()
    }
    items = []
    for m in MODULE_CATALOG:
        items.append(schemas.ModuleCatalogItem(
            slug=m["slug"],
            sector_group=m["sector_group"],
            min_plan=m["min_plan"],
            name_it=m["name_it"],
            name_en=m["name_en"],
            is_active_for_tenant=m["slug"] in active_slugs,
            unlocked=plan_meets_minimum(tenant.plan, m["min_plan"]),
        ))
    return items


@router.get("/catalog", response_model=List[schemas.ModuleCatalogItem])
def get_catalog(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Catalogo completo dei moduli, con lo stato di attivazione e di sblocco
    (in base al piano) per il tenant dell'utente loggato."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
    return _catalog_for_tenant(db, tenant)


@router.post("/{module_slug}", response_model=schemas.ModuleCatalogItem)
def activate_own_module(module_slug: str, db: Session = Depends(get_db),
                         admin: models.User = Depends(require_admin)):
    """Autoattivazione di un modulo da parte dell'amministratore del proprio
    tenant. Bloccata se il piano attuale non raggiunge il piano minimo del
    modulo (402 Payment Required, con il piano richiesto nel messaggio)."""
    module = MODULE_BY_SLUG.get(module_slug)
    if not module:
        raise HTTPException(status_code=404, detail="Modulo non trovato")
    tenant = db.query(models.Tenant).filter(models.Tenant.id == admin.tenant_id).first()
    if not plan_meets_minimum(tenant.plan, module["min_plan"]):
        raise HTTPException(
            status_code=402,
            detail=f"Questo modulo richiede almeno il piano '{module['min_plan']}'. Fai l'upgrade in Impostazioni > Abbonamento.",
        )
    existing = db.query(models.TenantModuleActivation).filter(
        models.TenantModuleActivation.tenant_id == tenant.id,
        models.TenantModuleActivation.module_id == module_slug,
    ).first()
    if not existing:
        db.add(models.TenantModuleActivation(tenant_id=tenant.id, module_id=module_slug, activated_by="admin"))
        db.commit()
    updated = _catalog_for_tenant(db, tenant)
    return next(m for m in updated if m.slug == module_slug)


@router.delete("/{module_slug}", response_model=schemas.ModuleCatalogItem)
def deactivate_own_module(module_slug: str, db: Session = Depends(get_db),
                           admin: models.User = Depends(require_admin)):
    module = MODULE_BY_SLUG.get(module_slug)
    if not module:
        raise HTTPException(status_code=404, detail="Modulo non trovato")
    db.query(models.TenantModuleActivation).filter(
        models.TenantModuleActivation.tenant_id == admin.tenant_id,
        models.TenantModuleActivation.module_id == module_slug,
    ).delete()
    db.commit()
    tenant = db.query(models.Tenant).filter(models.Tenant.id == admin.tenant_id).first()
    updated = _catalog_for_tenant(db, tenant)
    return next(m for m in updated if m.slug == module_slug)
