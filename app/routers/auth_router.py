"""Router di autenticazione e onboarding tenant (M11)."""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["Autenticazione"])


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "azienda"


DEFAULT_PIPELINE_STAGES = ["Nuovo Lead", "Contattato", "Proposta Inviata", "Trattativa", "Vinto", "Perso"]


@router.post("/register", response_model=schemas.Token)
def register_tenant(payload: schemas.TenantRegister, db: Session = Depends(get_db)):
    """Crea una nuova azienda cliente (tenant) con il primo utente amministratore.
    Corrisponde al wizard di onboarding descritto in Sezione 5.2 del documento."""
    existing = db.query(models.User).filter(models.User.email == payload.admin_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")

    base_slug = slugify(payload.company_name)
    slug = base_slug
    i = 1
    while db.query(models.Tenant).filter(models.Tenant.slug == slug).first():
        i += 1
        slug = f"{base_slug}-{i}"

    tenant = models.Tenant(
        name=payload.company_name,
        slug=slug,
        sector=payload.sector,
        default_language=payload.language,
    )
    db.add(tenant)
    db.flush()

    # Pipeline vendite di default, personalizzabile in seguito (M1)
    for idx, stage_name in enumerate(DEFAULT_PIPELINE_STAGES):
        db.add(models.PipelineStage(tenant_id=tenant.id, name=stage_name, order=idx))

    admin_user = models.User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        full_name=payload.admin_full_name,
        role=models.RoleEnum.admin,
        language=payload.language,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    token = create_access_token({"sub": admin_user.id, "tenant_id": tenant.id})
    return schemas.Token(access_token=token)


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o password non corrette")
    token = create_access_token({"sub": user.id, "tenant_id": user.tenant_id})
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
