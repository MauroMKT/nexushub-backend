"""Router del modulo pilota "Ristorazione & Hospitality" (Fase 9.1): prenotazioni
(tavolo per ristoranti/bar/locali, camera per hotel) e voci di menu.

Pagina condivisa "/hospitality" tra quattro settori affini (ristorazione,
bar_bistrot, locali_notturni, hotel): require_any_module lascia passare se
ALMENO uno di questi è attivo per il tenant."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_any_module

router = APIRouter(prefix="/hospitality", tags=["Ristorazione & Hospitality"])

_require = require_any_module("ristorazione", "bar_bistrot", "locali_notturni", "hotel")


def _reservation_to_out(r: models.Reservation, client_name: Optional[str] = None) -> schemas.ReservationOut:
    return schemas.ReservationOut(
        id=r.id, client_id=r.client_id, client_name=client_name, guest_name=r.guest_name,
        party_size=r.party_size, table_label=r.table_label, reservation_time=r.reservation_time,
        status=r.status, notes=r.notes, created_at=r.created_at,
    )


def _menu_item_to_out(m: models.MenuItem) -> schemas.MenuItemOut:
    return schemas.MenuItemOut(
        id=m.id, name=m.name, category=m.category, price=m.price,
        description=m.description, is_available=m.is_available, created_at=m.created_at,
    )


# ---------- Prenotazioni ----------
@router.get("/reservations", response_model=List[schemas.ReservationOut])
def list_reservations(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    reservations = db.query(models.Reservation).filter(
        models.Reservation.tenant_id == user.tenant_id
    ).order_by(models.Reservation.reservation_time.desc()).all()
    client_ids = {r.client_id for r in reservations if r.client_id}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_reservation_to_out(r, clients.get(r.client_id)) for r in reservations]


@router.post("/reservations", response_model=schemas.ReservationOut)
def create_reservation(payload: schemas.ReservationCreate, db: Session = Depends(get_db),
                        user: models.User = Depends(_require)):
    client_name = None
    if payload.client_id:
        client = db.query(models.Client).filter(
            models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente non trovato")
        client_name = client.name
    if not payload.client_id and not payload.guest_name:
        raise HTTPException(status_code=400, detail="Serve un cliente in anagrafica oppure il nome dell'ospite")
    reservation = models.Reservation(
        tenant_id=user.tenant_id, client_id=payload.client_id, guest_name=payload.guest_name,
        party_size=payload.party_size, table_label=payload.table_label,
        reservation_time=payload.reservation_time, status=payload.status, notes=payload.notes,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return _reservation_to_out(reservation, client_name)


@router.patch("/reservations/{reservation_id}", response_model=schemas.ReservationOut)
def update_reservation(reservation_id: str, payload: schemas.ReservationUpdate, db: Session = Depends(get_db),
                        user: models.User = Depends(_require)):
    reservation = db.query(models.Reservation).filter(
        models.Reservation.id == reservation_id, models.Reservation.tenant_id == user.tenant_id
    ).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(reservation, field, value)
    db.commit()
    db.refresh(reservation)
    client = db.query(models.Client).filter(models.Client.id == reservation.client_id).first() if reservation.client_id else None
    return _reservation_to_out(reservation, client.name if client else None)


@router.delete("/reservations/{reservation_id}")
def delete_reservation(reservation_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    reservation = db.query(models.Reservation).filter(
        models.Reservation.id == reservation_id, models.Reservation.tenant_id == user.tenant_id
    ).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")
    db.delete(reservation)
    db.commit()
    return {"ok": True}


# ---------- Menu ----------
@router.get("/menu-items", response_model=List[schemas.MenuItemOut])
def list_menu_items(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    items = db.query(models.MenuItem).filter(models.MenuItem.tenant_id == user.tenant_id).order_by(
        models.MenuItem.category, models.MenuItem.name
    ).all()
    return [_menu_item_to_out(m) for m in items]


@router.post("/menu-items", response_model=schemas.MenuItemOut)
def create_menu_item(payload: schemas.MenuItemCreate, db: Session = Depends(get_db),
                      user: models.User = Depends(_require)):
    item = models.MenuItem(
        tenant_id=user.tenant_id, name=payload.name, category=payload.category,
        price=payload.price, description=payload.description, is_available=payload.is_available,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _menu_item_to_out(item)


@router.patch("/menu-items/{item_id}", response_model=schemas.MenuItemOut)
def update_menu_item(item_id: str, payload: schemas.MenuItemUpdate, db: Session = Depends(get_db),
                      user: models.User = Depends(_require)):
    item = db.query(models.MenuItem).filter(
        models.MenuItem.id == item_id, models.MenuItem.tenant_id == user.tenant_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Voce di menu non trovata")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _menu_item_to_out(item)


@router.delete("/menu-items/{item_id}")
def delete_menu_item(item_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    item = db.query(models.MenuItem).filter(
        models.MenuItem.id == item_id, models.MenuItem.tenant_id == user.tenant_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Voce di menu non trovata")
    db.delete(item)
    db.commit()
    return {"ok": True}
