"""Router di autenticazione e onboarding tenant (M11)."""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..vat_utils import detect_vat_country

router = APIRouter(prefix="/auth", tags=["Autenticazione"])


@router.get("/vat-lookup", response_model=schemas.VatCountryInfo)
def vat_lookup(vat_number: str):
    """Riconosce il paese di una Partita IVA dal formato (nessuna chiamata VIES esterna).
    Usato dal form di registrazione per mostrare subito il paese rilevato e decidere
    se mostrare il campo PEC (solo aziende italiane)."""
    return detect_vat_country(vat_number)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "azienda"


DEFAULT_PIPELINE_STAGES = ["Nuovo Lead", "Contattato", "Proposta Inviata", "Trattativa", "Vinto", "Perso"]


@router.post("/register", response_model=schemas.Token)
def register_tenant(payload: schemas.TenantRegister, db: Session = Depends(get_db)):
    """Crea una nuova azienda cliente (tenant) con il primo utente amministratore.
    Supporta due tipi di registrazione: "azienda" (con dati societari, P.IVA, PEC)
    e "persona fisica" (solo anagrafica individuale)."""
    existing = db.query(models.User).filter(models.User.email == payload.admin_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")

    account_type = payload.account_type if payload.account_type in ("azienda", "persona_fisica") else "azienda"

    vat_country_code = None
    if account_type == "azienda":
        if not payload.legal_name:
            raise HTTPException(status_code=400, detail="La ragione sociale è obbligatoria per un account azienda")
        display_name = payload.legal_name
        # Riconoscimento del paese per il codice identificativo fiscale: la fonte
        # primaria è la selezione esplicita del paese nel form (più affidabile,
        # perché non dipende dal formato del numero che varia da stato a stato).
        # Se non è un codice ISO2 valido, fallback al vecchio riconoscimento dal
        # formato della P.IVA per retrocompatibilità con client non aggiornati.
        explicit_country = (payload.country or "").strip().upper()
        if len(explicit_country) == 2 and explicit_country.isalpha():
            vat_country_code = explicit_country
        elif payload.vat_number:
            vat_info = detect_vat_country(payload.vat_number)
            vat_country_code = vat_info["country_code"]
    else:
        if not payload.full_name:
            raise HTTPException(status_code=400, detail="Nome e cognome sono obbligatori per un account persona fisica")
        display_name = payload.full_name

    base_slug = slugify(display_name)
    slug = base_slug
    i = 1
    while db.query(models.Tenant).filter(models.Tenant.slug == slug).first():
        i += 1
        slug = f"{base_slug}-{i}"

    tenant = models.Tenant(
        name=display_name,
        slug=slug,
        sector=payload.sector if account_type == "azienda" else None,
        default_language=payload.language,
        account_type=models.AccountTypeEnum(account_type),
        address=payload.address,
        zip_code=payload.zip_code,
        country=payload.country,
        phone=payload.phone,
        email=payload.email,
        company_type=payload.company_type if account_type == "azienda" else None,
        trade_name=payload.trade_name if account_type == "azienda" else None,
        vat_number=payload.vat_number if account_type == "azienda" else None,
        vat_country_code=vat_country_code,
        pec=payload.pec if (account_type == "azienda" and vat_country_code == "IT") else None,
        contact_full_name=payload.contact_full_name if account_type == "azienda" else None,
        contact_phone=payload.contact_phone if account_type == "azienda" else None,
        contact_email=payload.contact_email if account_type == "azienda" else None,
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


@router.patch("/me", response_model=schemas.UserOut)
def update_me(payload: schemas.UserProfileUpdate, db: Session = Depends(get_db),
              current_user: models.User = Depends(get_current_user)):
    """Modifica i dati personali dell'utente loggato (nome, lingua, password)."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.language is not None:
        current_user.language = payload.language
    if payload.new_password:
        if not payload.current_password or not verify_password(payload.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Password attuale non corretta")
        current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user
