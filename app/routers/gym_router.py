"""Router del modulo pilota "Palestre e Centri Sportivi" (Fase 9.9).

Anagrafica soci con dati di contatto, tessere, corso/i di appartenenza (con
grado/cintura + anno per le arti marziali), certificato medico (check + upload
PDF/foto), altri documenti, foto socio, e trofei vinti per la classifica
sociale del club. Stesso pattern base64-in-DB usato per i documenti cliente
(Fase 8, client_documents_router.py): niente filesystem esterno."""
import base64
import binascii
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..module_access import require_module
from ..notifications import notify_tenant_admins

router = APIRouter(prefix="/gym", tags=["Palestre e Centri Sportivi"])

_require = require_module("palestre")

MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB, coerente con client_documents_router.py

# Il certificato medico deve essere un PDF o una foto (richiesta esplicita):
# niente Word/Excel/altri formati che poi nessuno riesce ad aprire in ambulatorio.
_MEDICAL_CERT_ALLOWED_TYPES = ("application/pdf",)


def _is_allowed_medical_cert_type(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return ct in _MEDICAL_CERT_ALLOWED_TYPES or ct.startswith("image/")


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


def _get_member_or_404(db: Session, tenant_id: str, member_id: str) -> models.GymMember:
    member = db.query(models.GymMember).filter(
        models.GymMember.id == member_id, models.GymMember.tenant_id == tenant_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Socio non trovato")
    return member


def _enrollments_out(db: Session, member_id: str) -> List[schemas.GymEnrollmentOut]:
    rows = (
        db.query(models.GymEnrollment, models.GymCourse)
        .join(models.GymCourse, models.GymEnrollment.course_id == models.GymCourse.id)
        .filter(models.GymEnrollment.member_id == member_id)
        .order_by(models.GymCourse.name)
        .all()
    )
    return [
        schemas.GymEnrollmentOut(
            id=e.id, member_id=e.member_id, course_id=e.course_id, course_name=c.name,
            is_martial_arts=c.is_martial_arts, grade_name=e.grade_name, grade_year=e.grade_year,
            enrolled_at=e.enrolled_at,
        )
        for e, c in rows
    ]


def _member_to_out(db: Session, member: models.GymMember) -> schemas.GymMemberOut:
    return schemas.GymMemberOut(
        id=member.id, client_id=member.client_id, full_name=member.full_name, phone=member.phone,
        email=member.email, address=member.address, birth_date=member.birth_date, fiscal_code=member.fiscal_code,
        vat_number=member.vat_number, card_number=member.card_number,
        federation_card_number=member.federation_card_number,
        medical_certificate_ok=member.medical_certificate_ok,
        medical_certificate_expiry=member.medical_certificate_expiry,
        has_photo=bool(member.photo_base64), notes=member.notes, created_at=member.created_at,
        enrollments=_enrollments_out(db, member.id),
    )


# ---------- Soci ----------
@router.get("/members", response_model=List[schemas.GymMemberOut])
def list_members(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    members = db.query(models.GymMember).filter(
        models.GymMember.tenant_id == user.tenant_id
    ).order_by(models.GymMember.full_name).all()
    return [_member_to_out(db, m) for m in members]


@router.post("/members", response_model=schemas.GymMemberOut)
def create_member(payload: schemas.GymMemberCreate, db: Session = Depends(get_db),
                   user: models.User = Depends(_require)):
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
    member = models.GymMember(
        tenant_id=user.tenant_id, client_id=payload.client_id, full_name=payload.full_name,
        phone=payload.phone, email=payload.email, address=payload.address, birth_date=payload.birth_date,
        fiscal_code=payload.fiscal_code, vat_number=payload.vat_number,
        card_number=payload.card_number, federation_card_number=payload.federation_card_number,
        medical_certificate_ok=payload.medical_certificate_ok,
        medical_certificate_expiry=payload.medical_certificate_expiry, notes=payload.notes,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


@router.get("/members/{member_id}", response_model=schemas.GymMemberOut)
def get_member(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    return _member_to_out(db, member)


@router.put("/members/{member_id}", response_model=schemas.GymMemberOut)
def update_member(member_id: str, payload: schemas.GymMemberUpdate, db: Session = Depends(get_db),
                   user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


@router.delete("/members/{member_id}")
def delete_member(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    db.delete(member)
    db.commit()
    return {"ok": True}


# ---------- Foto socio ----------
@router.post("/members/{member_id}/photo", response_model=schemas.GymMemberOut)
def upload_member_photo(member_id: str, payload: schemas.GymPhotoUpload, db: Session = Depends(get_db),
                         user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    if not (payload.content_type or "").lower().startswith("image/"):
        raise HTTPException(status_code=400, detail="La foto deve essere un'immagine (jpg, png, ecc.)")
    _decode_and_validate(payload.content_base64, MAX_PHOTO_SIZE_BYTES)
    member.photo_base64 = payload.content_base64
    member.photo_content_type = payload.content_type
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


@router.get("/members/{member_id}/photo", response_model=schemas.GymPhotoOut)
def get_member_photo(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    if not member.photo_base64:
        raise HTTPException(status_code=404, detail="Nessuna foto caricata per questo socio")
    return schemas.GymPhotoOut(content_type=member.photo_content_type or "image/jpeg", content_base64=member.photo_base64)


@router.delete("/members/{member_id}/photo", response_model=schemas.GymMemberOut)
def delete_member_photo(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    member.photo_base64 = None
    member.photo_content_type = None
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


# ---------- Corsi (catalogo estendibile) ----------
@router.get("/courses", response_model=List[schemas.GymCourseOut])
def list_courses(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    return db.query(models.GymCourse).filter(
        models.GymCourse.tenant_id == user.tenant_id
    ).order_by(models.GymCourse.name).all()


def _find_or_create_course(db: Session, tenant_id: str, name: str, is_martial_arts: bool) -> models.GymCourse:
    """Create-if-missing case-insensitive: se un corso con lo stesso nome esiste
    già per il tenant lo riusa (evita duplicati tipo "Karate" / "karate" / "KARATE"),
    così il catalogo corsi resta sempre completo e pulito nel tempo."""
    existing = db.query(models.GymCourse).filter(
        models.GymCourse.tenant_id == tenant_id,
        models.GymCourse.name.ilike(name.strip()),
    ).first()
    if existing:
        return existing
    course = models.GymCourse(tenant_id=tenant_id, name=name.strip(), is_martial_arts=is_martial_arts)
    db.add(course)
    db.flush()
    return course


@router.post("/courses", response_model=schemas.GymCourseOut)
def create_course(payload: schemas.GymCourseCreate, db: Session = Depends(get_db),
                   user: models.User = Depends(_require)):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Il nome del corso è obbligatorio")
    course = _find_or_create_course(db, user.tenant_id, payload.name, payload.is_martial_arts)
    db.commit()
    db.refresh(course)
    return course


# ---------- Iscrizioni ai corsi ----------
@router.post("/members/{member_id}/enrollments", response_model=schemas.GymMemberOut)
def create_enrollment(member_id: str, payload: schemas.GymEnrollmentCreate, db: Session = Depends(get_db),
                       user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)

    course: Optional[models.GymCourse] = None
    if payload.course_id:
        course = db.query(models.GymCourse).filter(
            models.GymCourse.id == payload.course_id, models.GymCourse.tenant_id == user.tenant_id
        ).first()
        if not course:
            raise HTTPException(status_code=404, detail="Corso non trovato")
    elif payload.course_name and payload.course_name.strip():
        course = _find_or_create_course(db, user.tenant_id, payload.course_name, payload.is_martial_arts)
    else:
        raise HTTPException(status_code=400, detail="Indica un corso esistente (course_id) oppure il nome di un corso nuovo (course_name)")

    already = db.query(models.GymEnrollment).filter(
        models.GymEnrollment.member_id == member_id, models.GymEnrollment.course_id == course.id
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="Il socio è già iscritto a questo corso")

    enrollment = models.GymEnrollment(
        tenant_id=user.tenant_id, member_id=member_id, course_id=course.id,
        grade_name=payload.grade_name if course.is_martial_arts else None,
        grade_year=payload.grade_year if course.is_martial_arts else None,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


@router.put("/members/{member_id}/enrollments/{enrollment_id}", response_model=schemas.GymMemberOut)
def update_enrollment(member_id: str, enrollment_id: str, payload: schemas.GymEnrollmentCreate,
                       db: Session = Depends(get_db), user: models.User = Depends(_require)):
    """Usato principalmente per aggiornare grado/anno (es. passaggio di cintura)."""
    member = _get_member_or_404(db, user.tenant_id, member_id)
    enrollment = db.query(models.GymEnrollment).filter(
        models.GymEnrollment.id == enrollment_id, models.GymEnrollment.member_id == member_id,
        models.GymEnrollment.tenant_id == user.tenant_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Iscrizione non trovata")
    course = db.query(models.GymCourse).filter(models.GymCourse.id == enrollment.course_id).first()
    if course and course.is_martial_arts:
        enrollment.grade_name = payload.grade_name
        enrollment.grade_year = payload.grade_year
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


@router.delete("/members/{member_id}/enrollments/{enrollment_id}", response_model=schemas.GymMemberOut)
def delete_enrollment(member_id: str, enrollment_id: str, db: Session = Depends(get_db),
                       user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    enrollment = db.query(models.GymEnrollment).filter(
        models.GymEnrollment.id == enrollment_id, models.GymEnrollment.member_id == member_id,
        models.GymEnrollment.tenant_id == user.tenant_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Iscrizione non trovata")
    db.delete(enrollment)
    db.commit()
    db.refresh(member)
    return _member_to_out(db, member)


# ---------- Documenti (certificato medico + altri) ----------
def _document_to_out(doc: models.GymDocument, uploaded_by_name: Optional[str] = None) -> schemas.GymDocumentOut:
    return schemas.GymDocumentOut(
        id=doc.id, member_id=doc.member_id, doc_type=doc.doc_type, filename=doc.filename,
        content_type=doc.content_type, size_bytes=doc.size_bytes,
        uploaded_by_name=uploaded_by_name, created_at=doc.created_at,
    )


@router.get("/members/{member_id}/documents", response_model=List[schemas.GymDocumentOut])
def list_member_documents(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_member_or_404(db, user.tenant_id, member_id)
    docs = db.query(models.GymDocument).filter(
        models.GymDocument.member_id == member_id, models.GymDocument.tenant_id == user.tenant_id
    ).order_by(models.GymDocument.created_at.desc()).all()
    uploader_ids = {d.uploaded_by_user_id for d in docs if d.uploaded_by_user_id}
    uploaders = {u.id: u.full_name for u in db.query(models.User).filter(models.User.id.in_(uploader_ids)).all()} if uploader_ids else {}
    return [_document_to_out(d, uploaders.get(d.uploaded_by_user_id)) for d in docs]


@router.post("/members/{member_id}/documents", response_model=schemas.GymDocumentOut)
def upload_member_document(member_id: str, payload: schemas.GymDocumentCreate, db: Session = Depends(get_db),
                            user: models.User = Depends(_require)):
    member = _get_member_or_404(db, user.tenant_id, member_id)
    if not payload.filename.strip():
        raise HTTPException(status_code=400, detail="Il nome del file è obbligatorio")
    doc_type = payload.doc_type if payload.doc_type in ("medical_certificate", "other") else "other"

    if doc_type == "medical_certificate" and not _is_allowed_medical_cert_type(payload.content_type):
        raise HTTPException(status_code=400, detail="Il certificato medico deve essere un PDF o una foto (jpg, png, ecc.)")

    raw = _decode_and_validate(payload.content_base64, MAX_DOCUMENT_SIZE_BYTES)
    doc = models.GymDocument(
        tenant_id=user.tenant_id, member_id=member_id, doc_type=doc_type,
        filename=payload.filename.strip(), content_type=payload.content_type or "application/octet-stream",
        size_bytes=len(raw), content_base64=payload.content_base64, uploaded_by_user_id=user.id,
    )
    db.add(doc)

    # Caricare il certificato medico lo marca automaticamente come "in regola":
    # collega il file al check si/no invece di lasciarli scollegati (l'utente
    # può comunque forzare il flag manualmente da PUT /members/{id} in ogni caso).
    if doc_type == "medical_certificate":
        member.medical_certificate_ok = True

    db.commit()
    db.refresh(doc)
    return _document_to_out(doc, user.full_name)


@router.get("/members/{member_id}/documents/{document_id}", response_model=schemas.GymDocumentContentOut)
def download_member_document(member_id: str, document_id: str, db: Session = Depends(get_db),
                              user: models.User = Depends(_require)):
    doc = db.query(models.GymDocument).filter(
        models.GymDocument.id == document_id, models.GymDocument.member_id == member_id,
        models.GymDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return schemas.GymDocumentContentOut(
        id=doc.id, filename=doc.filename, content_type=doc.content_type, content_base64=doc.content_base64,
    )


@router.delete("/members/{member_id}/documents/{document_id}")
def delete_member_document(member_id: str, document_id: str, db: Session = Depends(get_db),
                            user: models.User = Depends(_require)):
    doc = db.query(models.GymDocument).filter(
        models.GymDocument.id == document_id, models.GymDocument.member_id == member_id,
        models.GymDocument.tenant_id == user.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    db.delete(doc)
    db.commit()
    return {"ok": True}


# ---------- Trofei & classifica sociale ----------
@router.get("/members/{member_id}/trophies", response_model=List[schemas.GymTrophyOut])
def list_member_trophies(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    _get_member_or_404(db, user.tenant_id, member_id)
    return db.query(models.GymTrophy).filter(
        models.GymTrophy.member_id == member_id, models.GymTrophy.tenant_id == user.tenant_id
    ).order_by(models.GymTrophy.date_won.desc().nullslast()).all()


@router.post("/members/{member_id}/trophies", response_model=schemas.GymTrophyOut)
def create_trophy(member_id: str, payload: schemas.GymTrophyCreate, db: Session = Depends(get_db),
                   user: models.User = Depends(_require)):
    _get_member_or_404(db, user.tenant_id, member_id)
    trophy = models.GymTrophy(
        tenant_id=user.tenant_id, member_id=member_id, title=payload.title, placement=payload.placement,
        points=payload.points, date_won=payload.date_won, notes=payload.notes,
    )
    db.add(trophy)
    db.commit()
    db.refresh(trophy)
    return trophy


@router.delete("/members/{member_id}/trophies/{trophy_id}")
def delete_trophy(member_id: str, trophy_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    trophy = db.query(models.GymTrophy).filter(
        models.GymTrophy.id == trophy_id, models.GymTrophy.member_id == member_id,
        models.GymTrophy.tenant_id == user.tenant_id,
    ).first()
    if not trophy:
        raise HTTPException(status_code=404, detail="Trofeo non trovato")
    db.delete(trophy)
    db.commit()
    return {"ok": True}


@router.get("/leaderboard", response_model=List[schemas.GymLeaderboardEntryOut])
def leaderboard(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    """Classifica sociale: un socio compare se ha vinto almeno un trofeo,
    ordinata per punti totali (desc), poi per numero di trofei (desc)."""
    trophies = db.query(models.GymTrophy).filter(models.GymTrophy.tenant_id == user.tenant_id).all()
    if not trophies:
        return []

    by_member: dict = {}
    for tr in trophies:
        agg = by_member.setdefault(tr.member_id, {"count": 0, "points": 0})
        agg["count"] += 1
        agg["points"] += tr.points or 0

    member_ids = list(by_member.keys())
    members = {
        m.id: m for m in db.query(models.GymMember).filter(
            models.GymMember.id.in_(member_ids), models.GymMember.tenant_id == user.tenant_id
        ).all()
    }

    entries = []
    for member_id, agg in by_member.items():
        member = members.get(member_id)
        if not member:
            continue  # socio eliminato ma trofei rimasti orfani: non lo mostriamo
        entries.append(schemas.GymLeaderboardEntryOut(
            member_id=member.id, full_name=member.full_name, card_number=member.card_number,
            has_photo=bool(member.photo_base64), trophies_count=agg["count"], total_points=agg["points"],
        ))

    entries.sort(key=lambda e: (-e.total_points, -e.trophies_count, e.full_name))
    return entries


# ---------- Compleanni ----------
def _next_birthday(birth_date: date, today: date) -> date:
    """Prossima ricorrenza del compleanno a partire da oggi (se è oggi stesso,
    la ricorrenza restituita è oggi). Il 29 febbraio su un anno non bisestile
    viene festeggiato il 28 febbraio."""
    try:
        candidate = birth_date.replace(year=today.year)
    except ValueError:
        candidate = birth_date.replace(year=today.year, day=28)
    if candidate < today:
        try:
            candidate = birth_date.replace(year=today.year + 1)
        except ValueError:
            candidate = birth_date.replace(year=today.year + 1, day=28)
    return candidate


def _birthday_marker(member_id: str, on_date: date) -> str:
    return f"{member_id}:{on_date.isoformat()}"


def _maybe_notify_birthday_today(db: Session, tenant_id: str, member: models.GymMember, today: date) -> bool:
    """Notifica automaticamente il team quando un socio compie gli anni oggi,
    una sola volta al giorno per socio. Non serve uno scheduler in background:
    il controllo scatta ogni volta che qualcuno consulta GET /gym/birthdays
    (es. aprendo la scheda "Compleanni" del modulo), con dedupe sul giorno
    tramite Notification.related_id."""
    marker = _birthday_marker(member.id, today)
    already_sent = db.query(models.Notification).filter(
        models.Notification.tenant_id == tenant_id,
        models.Notification.related_type == "gym_birthday",
        models.Notification.related_id == marker,
    ).first()
    if already_sent:
        return True
    turning_age = today.year - member.birth_date.year
    notify_tenant_admins(
        db, tenant_id,
        title="🎂 Compleanno oggi",
        body=f"{member.full_name} compie {turning_age} anni oggi!",
        related_type="gym_birthday", related_id=marker,
    )
    return True


@router.get("/birthdays", response_model=List[schemas.GymBirthdayEntryOut])
def upcoming_birthdays(days_ahead: int = 30, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    """Prossimi compleanni entro `days_ahead` giorni (default 30), più vicino
    prima. Chi compie gli anni oggi fa scattare automaticamente la notifica
    al team (vedi _maybe_notify_birthday_today)."""
    today = date.today()
    members = db.query(models.GymMember).filter(
        models.GymMember.tenant_id == user.tenant_id, models.GymMember.birth_date.isnot(None)
    ).all()

    entries = []
    for member in members:
        next_bday = _next_birthday(member.birth_date, today)
        days_until = (next_bday - today).days
        if days_until > days_ahead:
            continue
        turning_age = next_bday.year - member.birth_date.year
        notified_today = _maybe_notify_birthday_today(db, user.tenant_id, member, today) if days_until == 0 else False
        entries.append(schemas.GymBirthdayEntryOut(
            member_id=member.id, full_name=member.full_name, card_number=member.card_number,
            has_photo=bool(member.photo_base64), birth_date=member.birth_date, next_birthday=next_bday,
            days_until=days_until, turning_age=turning_age, notified_today=notified_today,
        ))

    entries.sort(key=lambda e: e.days_until)
    return entries


@router.post("/members/{member_id}/birthday-notification")
def send_birthday_notification(member_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    """Invio manuale ed esplicito di una notifica di compleanno al team per un
    socio (es. per festeggiare in anticipo o rimandare il promemoria), a
    prescindere dal giorno esatto e senza limiti di dedupe come invece accade
    per la notifica automatica del giorno stesso."""
    member = _get_member_or_404(db, user.tenant_id, member_id)
    if not member.birth_date:
        raise HTTPException(status_code=400, detail="Il socio non ha una data di nascita registrata")
    today = date.today()
    turning_age = _next_birthday(member.birth_date, today).year - member.birth_date.year
    marker = f"{member.id}:{today.isoformat()}:manual:{models.gen_uuid()[:8]}"
    notify_tenant_admins(
        db, user.tenant_id,
        title="🎂 Promemoria compleanno",
        body=f"Ricordati di festeggiare {member.full_name} (compie {turning_age} anni)!",
        related_type="gym_birthday", related_id=marker,
    )
    return {"ok": True}
