"""Autenticazione JWT con isolamento multi-tenant (Sezione 4.1 del documento)."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Token del portale clienti: stesso schema OAuth2 ma con tokenUrl dedicato e claim "portal": true,
# così un token del portale non può essere usato per autenticarsi come membro del team e viceversa.
portal_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/portal/login", auto_error=False)


def _truncate_to_bcrypt_limit(password: str) -> str:
    """bcrypt supporta al massimo 72 byte: tronchiamo in modo sicuro (senza spezzare
    un carattere multi-byte a metà) per evitare un ValueError non gestito su
    password lunghe o con caratteri speciali/emoji."""
    encoded = password.encode("utf-8")
    if len(encoded) <= 72:
        return password
    return encoded[:72].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_truncate_to_bcrypt_limit(password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate_to_bcrypt_limit(plain), hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    # Un'azienda sospesa dal super admin perde l'accesso per tutti i suoi membri
    # (il super admin stesso vive nel tenant interno "_platform", sempre attivo).
    if user.role != models.RoleEnum.platform_admin:
        tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
        if tenant is None or not tenant.is_active:
            raise HTTPException(status_code=403, detail="Account sospeso: contatta l'assistenza")

    # Modalità "visualizza come super admin": il super admin resta autenticato
    # con la PROPRIA identità (id, email, ruolo) ma ogni endpoint che filtra per
    # tenant_id dell'utente corrente vede i dati del tenant scelto, grazie
    # all'header X-View-Tenant-Id inviato dal frontend quando è attiva la
    # modalità "Entra come" dal pannello Super Admin. Non genera mai un token
    # separato e non fa mai il login con le credenziali dell'iscritto: è
    # l'esatto opposto del vecchio /platform-admin/tenants/{id}/impersonate,
    # rimosso proprio perché avrebbe fatto "diventare" il super admin l'utente
    # del tenant. db.expunge stacca l'oggetto dalla sessione PRIMA di mutarlo,
    # così questa sovrascrittura resta solo in memoria per questa richiesta e
    # non può mai essere scritta per errore sul record reale dell'utente.
    if user.role == models.RoleEnum.platform_admin:
        view_tenant_id = request.headers.get("x-view-tenant-id")
        if view_tenant_id:
            target_tenant = db.query(models.Tenant).filter(models.Tenant.id == view_tenant_id).first()
            if target_tenant and target_tenant.slug != "_platform":
                db.expunge(user)
                user.tenant_id = target_tenant.id
                user.tenant = target_tenant

    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role not in (models.RoleEnum.admin, models.RoleEnum.platform_admin):
        raise HTTPException(status_code=403, detail="Operazione riservata agli amministratori del tenant")
    return user


def require_platform_admin(user: models.User = Depends(get_current_user)) -> models.User:
    """Unica eccezione consapevole all'isolamento tenant_id: il super admin può
    leggere/agire su tutti i tenant tramite gli endpoint dedicati in platform_admin_router."""
    if user.role != models.RoleEnum.platform_admin:
        raise HTTPException(status_code=403, detail="Operazione riservata al super admin della piattaforma")
    return user


def get_current_portal_client(token: str = Depends(portal_oauth2_scheme), db: Session = Depends(get_db)) -> models.Client:
    """Dipendenza equivalente a get_current_user ma per i login del portale clienti (M19).
    Il claim 'portal': true impedisce che un token del team venga riusato qui o viceversa."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessione del portale non valida",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if not payload.get("portal"):
            raise credentials_exception
        client_id: str = payload.get("client_id")
        if client_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise credentials_exception
    return client
