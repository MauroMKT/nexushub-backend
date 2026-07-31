"""Router dei moduli di settore attivabili (Fase 9).

Il catalogo dei moduli (quali esistono, in che settore, con che piano minimo)
è statico e vive in modules_catalog.py. QUALI moduli sono attivi per QUALE
tenant è invece dati vivi in models.TenantModuleActivation.

Un amministratore di tenant può autoattivare/disattivare un modulo solo se il
piano del proprio tenant raggiunge il piano minimo richiesto (min_plan); in
caso contrario riceve un 402 con l'indicazione del piano necessario, per
guidarlo verso l'upgrade in Impostazioni > Abbonamento. Il super admin bypassa
sempre questo limite tramite gli endpoint dedicati in platform_admin_router.py."""
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_admin
from ..config import settings
from ..database import get_db
from ..modules_catalog import (DEDICATED_ROUTES, MODULE_BY_SLUG, MODULE_CATALOG,
                                plan_meets_minimum)

router = APIRouter(prefix="/modules", tags=["Moduli di settore"])


def _catalog_for_tenant(db: Session, tenant: models.Tenant) -> List[schemas.ModuleCatalogItem]:
    activations: Dict[str, models.TenantModuleActivation] = {
        row.module_id: row
        for row in db.query(models.TenantModuleActivation)
        .filter(models.TenantModuleActivation.tenant_id == tenant.id)
        .all()
    }
    items = []
    for m in MODULE_CATALOG:
        activation = activations.get(m["slug"])
        items.append(schemas.ModuleCatalogItem(
            slug=m["slug"],
            sector_group=m["sector_group"],
            min_plan=m["min_plan"],
            name_it=m["name_it"],
            name_en=m["name_en"],
            is_active_for_tenant=activation is not None,
            unlocked=plan_meets_minimum(tenant.plan, m["min_plan"]),
            has_dedicated_feature=bool(m.get("has_dedicated_feature")),
            dedicated_route=DEDICATED_ROUTES.get(m["slug"]),
            purchased_standalone=bool(activation and activation.activated_by == "purchased"),
        ))
    return items


@router.get("/catalog", response_model=List[schemas.ModuleCatalogItem])
def get_catalog(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Catalogo completo dei moduli, con lo stato di attivazione e di sblocco
    (in base al piano) per il tenant dell'utente loggato."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
    return _catalog_for_tenant(db, tenant)


@router.get("/public-catalog", response_model=List[schemas.ModulePublicCatalogItem])
def get_public_catalog():
    """Versione minimale del catalogo, senza autenticazione: usata dal menu a
    tendina "Settore" nella pagina di registrazione, dove non esiste ancora
    un tenant/utente loggato. Nessun dato legato all'attivazione o al piano."""
    return [
        schemas.ModulePublicCatalogItem(
            slug=m["slug"], sector_group=m["sector_group"], name_it=m["name_it"], name_en=m["name_en"],
        )
        for m in MODULE_CATALOG
    ]


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


@router.post("/{module_slug}/checkout", response_model=schemas.CheckoutOut)
def checkout_module_addon(module_slug: str, db: Session = Depends(get_db),
                           admin: models.User = Depends(require_admin)):
    """Acquisto ricorrente del singolo modulo (Fase 9.2), indipendente dal piano:
    utile per un cliente che vuole solo un settore specifico senza fare l'upgrade
    dell'intero abbonamento. Crea un abbonamento Stripe dedicato a questo modulo
    (separato da quello di piano, se esiste): l'attivazione vera e propria avviene
    nel webhook /billing/webhook alla conferma del pagamento, non qui."""
    module = MODULE_BY_SLUG.get(module_slug)
    if not module:
        raise HTTPException(status_code=404, detail="Modulo non trovato")
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=400, detail="I pagamenti non sono ancora configurati: serve un account Stripe collegato al backend.")
    if not settings.stripe_price_module_addon:
        raise HTTPException(status_code=400, detail="Nessun price Stripe configurato per l'acquisto singolo dei moduli.")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == admin.tenant_id).first()
    existing = db.query(models.TenantModuleActivation).filter(
        models.TenantModuleActivation.tenant_id == tenant.id,
        models.TenantModuleActivation.module_id == module_slug,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Modulo già attivo per questa azienda")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    customer_id = tenant.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=admin.email, name=tenant.name, metadata={"tenant_id": tenant.id})
        customer_id = customer["id"]
        tenant.stripe_customer_id = customer_id
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_module_addon, "quantity": 1}],
        success_url=f"{settings.frontend_url}/modules?purchase=success",
        cancel_url=f"{settings.frontend_url}/modules?purchase=cancel",
        metadata={"tenant_id": tenant.id, "kind": "module_purchase", "module_slug": module_slug},
    )
    return schemas.CheckoutOut(checkout_url=session["url"])
