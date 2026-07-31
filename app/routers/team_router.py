"""Router M11 - Impostazioni, Team & Multilingua."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, hash_password, require_admin, verify_password
from ..config import settings
from ..database import get_db
from ..tenant_deletion import hard_delete_tenant

router = APIRouter(tags=["Impostazioni & Team"])


@router.get("/team", response_model=List[schemas.UserOut])
def list_team(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.User).filter(models.User.tenant_id == user.tenant_id).all()


@router.post("/team", response_model=schemas.UserOut)
def invite_team_member(payload: schemas.UserCreate, db: Session = Depends(get_db),
                        admin: models.User = Depends(require_admin)):
    """In produzione questo invia un invito via email; nell'MVP crea l'utente direttamente."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")
    new_user = models.User(
        tenant_id=admin.tenant_id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        language=payload.language,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/settings/tenant", response_model=schemas.TenantOut)
def get_tenant_settings(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
    return tenant


@router.put("/settings/tenant", response_model=schemas.TenantOut)
def update_tenant_settings(payload: schemas.TenantUpdate, db: Session = Depends(get_db),
                            admin: models.User = Depends(require_admin)):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == admin.tenant_id).first()
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/settings/tenant")
def delete_own_tenant(payload: schemas.TenantSelfDelete, db: Session = Depends(get_db),
                       admin: models.User = Depends(require_admin)):
    """Cancellazione permanente e irreversibile del proprio account/azienda,
    richiedibile solo dall'amministratore del tenant (non da un membro
    qualsiasi, vedi require_admin). Richiede la password corrente come
    conferma, per evitare cancellazioni accidentali o da sessioni compromesse.
    Cancella TUTTI i dati del tenant: clienti, trattative, fatture, chat,
    documenti, moduli attivati, utenti del team."""
    if admin.role == models.RoleEnum.platform_admin:
        raise HTTPException(status_code=400, detail="Il super admin non può cancellare il tenant della piattaforma da qui")
    if not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=400, detail="Password non corretta")
    hard_delete_tenant(db, admin.tenant_id)
    return {"status": "account cancellato"}


@router.get("/settings/languages")
def supported_languages():
    """Elenco lingue attive in questa fase (Sezione 6 del documento: IT/EN in Fase 1)."""
    return {"supported": settings.supported_languages, "default": settings.default_language}
