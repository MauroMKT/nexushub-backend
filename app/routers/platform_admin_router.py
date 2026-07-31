"""Router del super admin (platform_admin) - Fase 7.

Unica eccezione CONSAPEVOLE all'isolamento tenant_id che è la regola di
sicurezza più importante del progetto (vedi CLAUDE.md): ogni endpoint qui
attraversa deliberatamente tutti i tenant, protetto dalla dipendenza
require_platform_admin. Nessun altro router deve fare query multi-tenant."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, hash_password, require_platform_admin
from ..config import settings
from ..database import get_db
from ..modules_catalog import MODULE_BY_SLUG, MODULE_CATALOG, plan_meets_minimum
from ..tenant_deletion import hard_delete_tenant

router = APIRouter(prefix="/platform-admin", tags=["Super Admin"])

PLATFORM_TENANT_SLUG = "_platform"


def _get_or_create_platform_tenant(db: Session) -> models.Tenant:
    tenant = db.query(models.Tenant).filter(models.Tenant.slug == PLATFORM_TENANT_SLUG).first()
    if not tenant:
        tenant = models.Tenant(
            name="NexusHub Platform",
            slug=PLATFORM_TENANT_SLUG,
            account_type=models.AccountTypeEnum.azienda,
            plan="enterprise",
        )
        db.add(tenant)
        db.flush()
    return tenant


@router.post("/bootstrap", response_model=schemas.Token)
def bootstrap_platform_admin(payload: schemas.PlatformAdminBootstrap, db: Session = Depends(get_db)):
    """Crea il PRIMO super admin. Funziona solo se PLATFORM_ADMIN_BOOTSTRAP_SECRET
    è impostata sul backend, il segreto fornito corrisponde, e non esiste già
    nessun platform_admin (per evitare che chiunque possa auto-promuoversi)."""
    if not settings.platform_admin_bootstrap_secret:
        raise HTTPException(status_code=403, detail="Bootstrap non configurato sul server")
    if payload.secret != settings.platform_admin_bootstrap_secret:
        raise HTTPException(status_code=403, detail="Segreto di bootstrap non valido")

    existing_admin = db.query(models.User).filter(models.User.role == models.RoleEnum.platform_admin).first()
    if existing_admin:
        raise HTTPException(status_code=400, detail="Esiste già un super admin: usa /platform-admin/admins per aggiungerne altri")

    existing_email = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già registrata")

    tenant = _get_or_create_platform_tenant(db)
    user = models.User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=models.RoleEnum.platform_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "tenant_id": tenant.id})
    return schemas.Token(access_token=token)


@router.post("/admins", response_model=schemas.UserOut)
def create_platform_admin(payload: schemas.PlatformAdminCreate, db: Session = Depends(get_db),
                           _admin: models.User = Depends(require_platform_admin)):
    """Un super admin esistente può crearne altri."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")
    tenant = _get_or_create_platform_tenant(db)
    user = models.User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=models.RoleEnum.platform_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/stats", response_model=schemas.PlatformStats)
def platform_stats(db: Session = Depends(get_db), _admin: models.User = Depends(require_platform_admin)):
    tenants = db.query(models.Tenant).filter(models.Tenant.slug != PLATFORM_TENANT_SLUG).all()
    by_plan = {}
    for t in tenants:
        by_plan[t.plan] = by_plan.get(t.plan, 0) + 1
    return schemas.PlatformStats(
        total_tenants=len(tenants),
        active_tenants=sum(1 for t in tenants if t.is_active),
        suspended_tenants=sum(1 for t in tenants if not t.is_active),
        total_users=db.query(models.User).join(models.Tenant).filter(models.Tenant.slug != PLATFORM_TENANT_SLUG).count(),
        total_clients=db.query(models.Client).count(),
        tenants_by_plan=by_plan,
    )


@router.get("/tenants", response_model=List[schemas.PlatformTenantOut])
def list_all_tenants(db: Session = Depends(get_db), _admin: models.User = Depends(require_platform_admin)):
    """Attraversa TUTTI i tenant: questa è la vista che permette al super admin
    di vedere ogni azienda/cliente collegato alla piattaforma."""
    tenants = db.query(models.Tenant).filter(models.Tenant.slug != PLATFORM_TENANT_SLUG).order_by(models.Tenant.created_at.desc()).all()
    results = []
    for t in tenants:
        user_count = db.query(models.User).filter(models.User.tenant_id == t.id).count()
        client_count = db.query(models.Client).filter(models.Client.tenant_id == t.id).count()
        out = schemas.PlatformTenantOut.model_validate(t)
        out.user_count = user_count
        out.client_count = client_count
        results.append(out)
    return results


@router.get("/tenants/{tenant_id}", response_model=schemas.PlatformTenantOut)
def get_tenant_detail(tenant_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_platform_admin)):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    out = schemas.PlatformTenantOut.model_validate(tenant)
    out.user_count = db.query(models.User).filter(models.User.tenant_id == tenant.id).count()
    out.client_count = db.query(models.Client).filter(models.Client.tenant_id == tenant.id).count()
    return out


@router.put("/tenants/{tenant_id}", response_model=schemas.PlatformTenantOut)
def update_any_tenant(tenant_id: str, payload: schemas.PlatformTenantUpdate, db: Session = Depends(get_db),
                      _admin: models.User = Depends(require_platform_admin)):
    """Agisce su un tenant qualsiasi: sospensione, cambio piano, rinomina."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    out = schemas.PlatformTenantOut.model_validate(tenant)
    out.user_count = db.query(models.User).filter(models.User.tenant_id == tenant.id).count()
    out.client_count = db.query(models.Client).filter(models.Client.tenant_id == tenant.id).count()
    return out


@router.get("/tenants/{tenant_id}/users", response_model=List[schemas.UserOut])
def list_tenant_users(tenant_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_platform_admin)):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    return db.query(models.User).filter(models.User.tenant_id == tenant_id).all()


@router.delete("/tenants/{tenant_id}")
def suspend_tenant(tenant_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_platform_admin)):
    """Non cancella i dati: sospende l'accesso (is_active=False). Reversibile
    riattivando il tenant. Per la cancellazione DEFINITIVA vedi l'endpoint
    /tenants/{tenant_id}/permanent qui sotto."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    tenant.is_active = False
    db.commit()
    return {"status": "sospeso"}


@router.delete("/tenants/{tenant_id}/permanent")
def delete_tenant_permanently(tenant_id: str, db: Session = Depends(get_db),
                               _admin: models.User = Depends(require_platform_admin)):
    """Cancellazione DEFINITIVA e irreversibile di un tenant e di tutti i suoi
    dati (utenti, clienti, trattative, fatture, chat, documenti, moduli
    attivati, ecc.). Diversa dalla sospensione: qui non c'è modo di tornare
    indietro. Il frontend richiede una doppia conferma esplicita prima di
    chiamare questo endpoint."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    if tenant.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(status_code=400, detail="Non è possibile cancellare il tenant interno della piattaforma")
    hard_delete_tenant(db, tenant_id)
    return {"status": "cancellato definitivamente"}


# ---------- Moduli di settore per un tenant specifico (Fase 9) ----------
@router.get("/tenants/{tenant_id}/modules", response_model=List[schemas.ModuleCatalogItem])
def list_tenant_modules(tenant_id: str, db: Session = Depends(get_db),
                         _admin: models.User = Depends(require_platform_admin)):
    """Catalogo completo dei moduli con lo stato di attivazione per QUESTO
    tenant. Il campo 'unlocked' è sempre True qui: il super admin può
    attivare qualunque modulo per qualunque tenant a prescindere dal piano."""
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    active_slugs = {
        row.module_id
        for row in db.query(models.TenantModuleActivation.module_id)
        .filter(models.TenantModuleActivation.tenant_id == tenant_id).all()
    }
    return [
        schemas.ModuleCatalogItem(
            slug=m["slug"], sector_group=m["sector_group"], min_plan=m["min_plan"],
            name_it=m["name_it"], name_en=m["name_en"],
            is_active_for_tenant=m["slug"] in active_slugs, unlocked=True,
        )
        for m in MODULE_CATALOG
    ]


@router.post("/tenants/{tenant_id}/modules/{module_slug}")
def activate_tenant_module(tenant_id: str, module_slug: str, db: Session = Depends(get_db),
                            _admin: models.User = Depends(require_platform_admin)):
    """Il super admin attiva un modulo per un tenant qualsiasi, a prescindere
    dal piano: utile per sbloccare una funzionalità in trattativa commerciale
    prima ancora che il cliente faccia l'upgrade."""
    if module_slug not in MODULE_BY_SLUG:
        raise HTTPException(status_code=404, detail="Modulo non trovato")
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    existing = db.query(models.TenantModuleActivation).filter(
        models.TenantModuleActivation.tenant_id == tenant_id,
        models.TenantModuleActivation.module_id == module_slug,
    ).first()
    if not existing:
        db.add(models.TenantModuleActivation(tenant_id=tenant_id, module_id=module_slug, activated_by="platform_admin"))
        db.commit()
    return {"status": "attivato"}


@router.delete("/tenants/{tenant_id}/modules/{module_slug}")
def deactivate_tenant_module(tenant_id: str, module_slug: str, db: Session = Depends(get_db),
                              _admin: models.User = Depends(require_platform_admin)):
    db.query(models.TenantModuleActivation).filter(
        models.TenantModuleActivation.tenant_id == tenant_id,
        models.TenantModuleActivation.module_id == module_slug,
    ).delete()
    db.commit()
    return {"status": "disattivato"}
