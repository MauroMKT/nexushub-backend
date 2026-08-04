"""Router del modulo pilota "Agenzie Immobiliari" (Fase 9.1, esteso in Fase
9.13): portafoglio immobili con tipo, indirizzo/città, superficie, camere/
bagni, piani, tipo contratto (vendita/locazione), prezzo e prezzo di
valutazione, stato immobile, disponibilità a riscatto, preferenza visite,
galleria foto, documenti e video — collegabile a un cliente (proprietario o
interessato) già in anagrafica. Foto/documenti/video usano lo stesso pattern
base64-in-DB del modulo Palestre (gym_router.py): niente filesystem esterno
persistente su Railway."""
import base64
import binascii
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_module

router = APIRouter(prefix="/real-estate/properties", tags=["Agenzie Immobiliari"])

_require = require_module("agenzie_immobiliari")

MAX_PHOTO_SIZE_BYTES = 12 * 1024 * 1024  # 12 MB, come modulo Palestre
MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB: planimetrie/atti scansionati
MAX_VIDEO_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB: pensato per clip brevi, non tour lunghi
# Per video più lunghi conviene il campo video_url (link esterno YouTube/Instagram/tour 3D)
# piuttosto che caricare il file: niente CDN/storage dedicato in questo MVP.


def _decode_and_validate(content_base64: str, max_size: int) -> bytes:
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Contenuto file non valido (base64 atteso)")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Il file è vuoto")
    if len(raw) > max_size:
        raise HTTPException(status_code=400, detail=f"Il file supera la dimensione massima consentita ({max_size // (1024*1024)} MB)")
    return raw


def _get_property_or_404(db: Session, tenant_id: str, property_id: str) -> models.RealEstateProperty:
    prop = db.query(models.RealEstateProperty).filter(
        models.RealEstateProperty.id == property_id, models.RealEstateProperty.tenant_id == tenant_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Immobile non trovato")
    return prop


def _photo_count(db: Session, property_id: str) -> int:
    return db.query(models.RealEstatePhoto).filter(models.RealEstatePhoto.property_id == property_id).count()


def _to_out(db: Session, p: models.RealEstateProperty, client_name: Optional[str] = None) -> schemas.RealEstatePropertyOut:
    return schemas.RealEstatePropertyOut(
        id=p.id, title=p.title, client_id=p.client_id, client_name=client_name,
        property_type=p.property_type, address=p.address, city=p.city, size_sqm=p.size_sqm,
        rooms=p.rooms, bathrooms=p.bathrooms, building_floor=p.building_floor, unit_floor=p.unit_floor,
        contract_type=p.contract_type or "vendita", price=p.price, valuation_price=p.valuation_price,
        status=p.status, condition_state=p.condition_state, visit_availability=p.visit_availability,
        rent_to_own=bool(p.rent_to_own), video_url=p.video_url, photo_count=_photo_count(db, p.id),
        notes=p.notes, created_at=p.created_at,
    )


@router.get("", response_model=List[schemas.RealEstatePropertyOut])
def list_properties(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    properties = db.query(models.RealEstateProperty).filter(
        models.RealEstateProperty.tenant_id == user.tenant_id
    ).order_by(models.RealEstateProperty.created_at.desc()).all()
    client_ids = {p.client_id for p in properties if p.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_to_out(db, p, clients.get(p.client_id)) for p in properties]


@router.post("", response_model=schemas.RealEstatePropertyOut)
def create_property(payload: schemas.RealEstatePropertyCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    client_name = None
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
        client_name = client.name
    prop = models.RealEstateProperty(
        tenant_id=user.tenant_id, client_id=payload.client_id, title=payload.title,
        property_type=payload.property_type, address=payload.address, city=payload.city,
        size_sqm=payload.size_sqm, rooms=payload.rooms, bathrooms=payload.bathrooms,
        building_floor=payload.building_floor, unit_floor=payload.unit_floor,
        contract_type=payload.contract_type, price=payload.price, valuation_price=payload.valuation_price,
        status=payload.status, condition_state=payload.condition_state,
        visit_availability=payload.visit_availability, rent_to_own=payload.rent_to_own,
        video_url=payload.video_url, notes=payload.notes,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _to_out(db, prop, client_name)


@router.patch("/{property_id}", response_model=schemas.RealEstatePropertyOut)
def update_property(property_id: str, payload: schemas.RealEstatePropertyUpdate, db: Session = Depends(get_db),
                     user: models.User = Depends(_require)):
    prop = _get_property_or_404(db, user.tenant_id, property_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(prop, field, value)
    db.commit()
    db.refresh(prop)
    client = db.query(models.Client).filter(models.Client.id == prop.client_id).first() if prop.client_id else None
    return _to_out(db, prop, client.name if client else None)


@router.delete("/{property_id}")
def delete_property(property_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    prop = _get_property_or_404(db, user.tenant_id, property_id)
    db.delete(prop)
    db.commit()
    return {"ok": True}


# ---------- Galleria foto ----------
@router.get("/{property_id}/photos", response_model=List[schemas.RealEstatePhotoOut])
def list_property_photos(property_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_property_or_404(db, user.tenant_id, property_id)
    return db.query(models.RealEstatePhoto).filter(
        models.RealEstatePhoto.property_id == property_id, models.RealEstatePhoto.tenant_id == user.tenant_id
    ).order_by(models.RealEstatePhoto.created_at).all()


@router.post("/{property_id}/photos", response_model=schemas.RealEstatePhotoOut)
def upload_property_photo(property_id: str, payload: schemas.RealEstatePhotoUpload, db: Session = Depends(get_db),
                           user: models.User = Depends(_require)):
    _get_property_or_404(db, user.tenant_id, property_id)
    if not (payload.content_type or "").lower().startswith("image/"):
        raise HTTPException(status_code=400, detail="La foto deve essere un'immagine (jpg, png, ecc.)")
    raw = _decode_and_validate(payload.content_base64, MAX_PHOTO_SIZE_BYTES)
    photo = models.RealEstatePhoto(
        tenant_id=user.tenant_id, property_id=property_id, content_type=payload.content_type,
        size_bytes=len(raw), content_base64=payload.content_base64,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.get("/{property_id}/photos/{photo_id}", response_model=schemas.RealEstatePhotoContentOut)
def download_property_photo(property_id: str, photo_id: str, db: Session = Depends(get_db),
                             user: models.User = Depends(_require)):
    photo = db.query(models.RealEstatePhoto).filter(
        models.RealEstatePhoto.id == photo_id, models.RealEstatePhoto.property_id == property_id,
        models.RealEstatePhoto.tenant_id == user.tenant_id,
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto non trovata")
    return schemas.RealEstatePhotoContentOut(
        id=photo.id, content_type=photo.content_type, content_base64=photo.content_base64,
    )


@router.delete("/{property_id}/photos/{photo_id}")
def delete_property_photo(property_id: str, photo_id: str, db: Session = Depends(get_db),
                           user: models.User = Depends(_require)):
    photo = db.query(models.RealEstatePhoto).filter(
        models.RealEstatePhoto.id == photo_id, models.RealEstatePhoto.property_id == property_id,
        models.RealEstatePhoto.tenant_id == user.tenant_id,
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto non trovata")
    db.delete(photo)
    db.commit()
    return {"ok": True}


# ---------- Documenti e video ----------
def _document_to_out(doc: models.RealEstateDocument, uploaded_by_name: Optional[str] = None) -> schemas.RealEstateDocumentOut:
    return schemas.RealEstateDocumentOut(
        id=doc.id, property_id=doc.property_id, doc_type=doc.doc_type, filename=doc.filename,
        content_type=doc.content_type, size_bytes=doc.size_bytes,
        uploaded_by_name=uploaded_by_name, created_at=doc.created_at,
    )


@router.get("/{property_id}/documents", response_model=List[schemas.RealEstateDocumentOut])
def list_property_documents(property_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_property_or_404(db, user.tenant_id, property_id)
    docs = db.query(models.RealEstateDocument).filter(
        models.RealEstateDocument.property_id == property_id, models.RealEstateDocument.tenant_id == user.tenant_id
    ).order_by(models.RealEstateDocument.created_at.desc()).all()
    uploader_ids = {d.uploaded_by_user_id for d in docs if d.uploaded_by_user_id}
    uploaders = {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(uploader_ids)).all()} if uploader_ids else {}
    return [_document_to_out(d, uploaders.get(d.uploaded_by_user_id)) for d in docs]


@router.post("/{property_id}/documents", response_model=schemas.RealEstateDocumentOut)
def upload_property_document(property_id: str, payload: schemas.RealEstateDocumentCreate, db: Session = Depends(get_db),
                              user: models.User = Depends(_require)):
    _get_property_or_404(db, user.tenant_id, property_id)
    if not payload.filename.strip():
        raise HTTPException(status_code=400, detail="Il nome del file è obbligatorio")
    doc_type = payload.doc_type if payload.doc_type in ("documento", "video") else "documento"

    if doc_type == "video" and not (payload.content_type or "").lower().startswith("video/"):
        raise HTTPException(status_code=400, detail="Il video deve essere un file video (mp4, mov, ecc.)")

    max_size = MAX_VIDEO_SIZE_BYTES if doc_type == "video" else MAX_DOCUMENT_SIZE_BYTES
    raw = _decode_and_validate(payload.content_base64, max_size)
    doc = models.RealEstateDocument(
        tenant_id=user.tenant_id, property_id=property_id, doc_type=doc_type,
        filename=payload.filename.strip(), content_type=payload.content_type or "application/octet-stream",
        size_bytes=len(raw), content_base64=payload.content_base64, uploaded_by_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _document_to_out(doc, user.full_name)


@router.get("/{property_id}/documents/{document_id}", response_model=schemas.RealEstateDocumentContentOut)
def download_property_document(property_id: str, document_id: str, db: Session = Depends(get_db),
                                user: models.User = Depends(_require)):
    doc = db.query(models.RealEstateDocument).filter(
        models.RealEstateDocument.id == document_id, models.RealEstateDocument.property_id == property_id,
        models.RealEstateDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return schemas.RealEstateDocumentContentOut(
        id=doc.id, filename=doc.filename, content_type=doc.content_type, content_base64=doc.content_base64,
    )


@router.delete("/{property_id}/documents/{document_id}")
def delete_property_document(property_id: str, document_id: str, db: Session = Depends(get_db),
                              user: models.User = Depends(_require)):
    doc = db.query(models.RealEstateDocument).filter(
        models.RealEstateDocument.id == document_id, models.RealEstateDocument.property_id == property_id,
        models.RealEstateDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    db.delete(doc)
    db.commit()
    return {"ok": True}
