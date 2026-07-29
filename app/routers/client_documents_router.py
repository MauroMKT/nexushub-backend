"""Documenti nella scheda cliente (Fase 8).

Il contenuto file è salvato come base64 in DB (niente filesystem esterno, coerente
con deploy su piattaforme dal filesystem non garantito persistente). Le liste
restituiscono solo i metadati (niente content_base64): il contenuto si scarica
con un endpoint dedicato per evitare payload enormi su ogni GET /documents.

Due gruppi di endpoint sullo stesso dato:
- lato team (sotto /clients/{client_id}/documents, auth normale, filtrato per tenant)
- lato portale clienti (sotto /portal/documents, sola lettura, M19)
"""
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_portal_client, get_current_user
from ..database import get_db

MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB: limite prudente per contenuto salvato in DB

team_router = APIRouter(prefix="/clients", tags=["Documenti cliente"])
portal_router = APIRouter(prefix="/portal", tags=["Documenti cliente"])


def _to_out(doc: models.ClientDocument, uploaded_by_name: str = None) -> schemas.ClientDocumentOut:
    return schemas.ClientDocumentOut(
        id=doc.id, client_id=doc.client_id, filename=doc.filename, content_type=doc.content_type,
        size_bytes=doc.size_bytes, uploaded_by_name=uploaded_by_name, created_at=doc.created_at,
    )


def _decode_and_validate(content_base64: str) -> bytes:
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Contenuto file non valido (base64 atteso)")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Il file è vuoto")
    if len(raw) > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Il file supera la dimensione massima consentita (10 MB)")
    return raw


# ---------- Lato team ----------
@team_router.get("/{client_id}/documents", response_model=list[schemas.ClientDocumentOut])
def list_client_documents(client_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(models.Client.id == client_id, models.Client.tenant_id == user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    docs = (
        db.query(models.ClientDocument)
        .filter(models.ClientDocument.client_id == client_id, models.ClientDocument.tenant_id == user.tenant_id)
        .order_by(models.ClientDocument.created_at.desc())
        .all()
    )
    uploader_ids = {d.uploaded_by_user_id for d in docs if d.uploaded_by_user_id}
    uploaders = {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(uploader_ids)).all()} if uploader_ids else {}
    return [_to_out(d, uploaders.get(d.uploaded_by_user_id)) for d in docs]


@team_router.post("/{client_id}/documents", response_model=schemas.ClientDocumentOut)
def upload_client_document(client_id: str, payload: schemas.ClientDocumentCreate, db: Session = Depends(get_db),
                            user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(models.Client.id == client_id, models.Client.tenant_id == user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    if not payload.filename.strip():
        raise HTTPException(status_code=400, detail="Il nome del file è obbligatorio")

    raw = _decode_and_validate(payload.content_base64)
    doc = models.ClientDocument(
        tenant_id=user.tenant_id, client_id=client_id, uploaded_by_user_id=user.id,
        filename=payload.filename.strip(), content_type=payload.content_type or "application/octet-stream",
        size_bytes=len(raw), content_base64=payload.content_base64,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _to_out(doc, user.full_name)


@team_router.get("/{client_id}/documents/{document_id}", response_model=schemas.ClientDocumentContentOut)
def download_client_document(client_id: str, document_id: str, db: Session = Depends(get_db),
                              user: models.User = Depends(get_current_user)):
    doc = db.query(models.ClientDocument).filter(
        models.ClientDocument.id == document_id, models.ClientDocument.client_id == client_id,
        models.ClientDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return schemas.ClientDocumentContentOut(
        id=doc.id, filename=doc.filename, content_type=doc.content_type, content_base64=doc.content_base64,
    )


@team_router.delete("/{client_id}/documents/{document_id}")
def delete_client_document(client_id: str, document_id: str, db: Session = Depends(get_db),
                            user: models.User = Depends(get_current_user)):
    doc = db.query(models.ClientDocument).filter(
        models.ClientDocument.id == document_id, models.ClientDocument.client_id == client_id,
        models.ClientDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    db.delete(doc)
    db.commit()
    return {"ok": True}


# ---------- Lato portale clienti (sola lettura) ----------
@portal_router.get("/documents", response_model=list[schemas.ClientDocumentOut])
def list_client_documents_portal_side(db: Session = Depends(get_db), client: models.Client = Depends(get_current_portal_client)):
    docs = (
        db.query(models.ClientDocument)
        .filter(models.ClientDocument.client_id == client.id)
        .order_by(models.ClientDocument.created_at.desc())
        .all()
    )
    uploader_ids = {d.uploaded_by_user_id for d in docs if d.uploaded_by_user_id}
    uploaders = {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(uploader_ids)).all()} if uploader_ids else {}
    return [_to_out(d, uploaders.get(d.uploaded_by_user_id, "Team")) for d in docs]


@portal_router.get("/documents/{document_id}", response_model=schemas.ClientDocumentContentOut)
def download_client_document_portal_side(document_id: str, db: Session = Depends(get_db),
                                          client: models.Client = Depends(get_current_portal_client)):
    doc = db.query(models.ClientDocument).filter(
        models.ClientDocument.id == document_id, models.ClientDocument.client_id == client.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return schemas.ClientDocumentContentOut(
        id=doc.id, filename=doc.filename, content_type=doc.content_type, content_base64=doc.content_base64,
    )
