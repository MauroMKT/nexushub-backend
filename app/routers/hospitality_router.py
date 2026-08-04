"""Router del modulo pilota "Ristorazione & Hospitality" (Fase 9.1, esteso in
Fase 9.15 con un vero POS ristorante): prenotazioni (tavolo per ristoranti/
bar/locali, camera per hotel), voci di menu, mappa tavoli, comande cucina/
asporto/delivery e gestione conto.

Pagina condivisa "/hospitality" tra quattro settori affini (ristorazione,
bar_bistrot, locali_notturni, hotel): require_any_module lascia passare se
ALMENO uno di questi è attivo per il tenant. HospitalityProfile.business_type
(scelto dall'utente con un menu a tendina, non legato al piano/modulo
acquistato) decide se la pagina mostra il set "ristorante" (tavoli, cucina,
delivery, ordini, conto) o il set "hotel" (solo prenotazioni camere + menu)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..module_access import require_any_module

router = APIRouter(prefix="/hospitality", tags=["Ristorazione & Hospitality"])

_require = require_any_module("ristorazione", "bar_bistrot", "locali_notturni", "hotel")


def _get_or_create_profile(db: Session, tenant_id: str) -> models.HospitalityProfile:
    profile = db.query(models.HospitalityProfile).filter(
        models.HospitalityProfile.tenant_id == tenant_id
    ).first()
    if not profile:
        profile = models.HospitalityProfile(tenant_id=tenant_id, business_type="ristorante")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


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


# ---------- Profilo attività (ristorante / hotel) ----------
@router.get("/profile", response_model=schemas.HospitalityProfileOut)
def get_profile(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    return _get_or_create_profile(db, user.tenant_id)


@router.put("/profile", response_model=schemas.HospitalityProfileOut)
def update_profile(payload: schemas.HospitalityProfileUpdate, db: Session = Depends(get_db),
                    user: models.User = Depends(_require)):
    if payload.business_type not in ("ristorante", "hotel"):
        raise HTTPException(status_code=400, detail="Tipo attività non valido")
    profile = _get_or_create_profile(db, user.tenant_id)
    profile.business_type = payload.business_type
    db.commit()
    db.refresh(profile)
    return profile


# ---------- Mappa tavoli ----------
def _table_to_out(db: Session, table: models.RestaurantTable) -> schemas.RestaurantTableOut:
    open_orders = db.query(models.KitchenOrder).filter(
        models.KitchenOrder.table_id == table.id,
        models.KitchenOrder.bill_id.is_(None),
        models.KitchenOrder.status != "annullato",
    ).count()
    return schemas.RestaurantTableOut(
        id=table.id, label=table.label, seats=table.seats, pos_x=table.pos_x, pos_y=table.pos_y,
        occupied=open_orders > 0, open_order_count=open_orders,
    )


@router.get("/tables", response_model=List[schemas.RestaurantTableOut])
def list_tables(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    tables = db.query(models.RestaurantTable).filter(
        models.RestaurantTable.tenant_id == user.tenant_id
    ).order_by(models.RestaurantTable.label).all()
    return [_table_to_out(db, t) for t in tables]


@router.post("/tables", response_model=schemas.RestaurantTableOut)
def create_table(payload: schemas.RestaurantTableCreate, db: Session = Depends(get_db),
                  user: models.User = Depends(_require)):
    table = models.RestaurantTable(
        tenant_id=user.tenant_id, label=payload.label, seats=payload.seats,
        pos_x=payload.pos_x, pos_y=payload.pos_y,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return _table_to_out(db, table)


@router.patch("/tables/{table_id}", response_model=schemas.RestaurantTableOut)
def update_table(table_id: str, payload: schemas.RestaurantTableUpdate, db: Session = Depends(get_db),
                  user: models.User = Depends(_require)):
    table = db.query(models.RestaurantTable).filter(
        models.RestaurantTable.id == table_id, models.RestaurantTable.tenant_id == user.tenant_id
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Tavolo non trovato")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(table, field, value)
    db.commit()
    db.refresh(table)
    return _table_to_out(db, table)


@router.delete("/tables/{table_id}")
def delete_table(table_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    table = db.query(models.RestaurantTable).filter(
        models.RestaurantTable.id == table_id, models.RestaurantTable.tenant_id == user.tenant_id
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Tavolo non trovato")
    db.delete(table)
    db.commit()
    return {"ok": True}


# ---------- Comande (tavolo, asporto, delivery) — condividono lo stesso flusso
# di stati così un'unica schermata "Cucina" li gestisce tutti insieme ----------
_ORDER_STATUSES = ("in_attesa", "in_preparazione", "pronto", "consegnato", "annullato")


def _order_to_out(order: models.KitchenOrder, table_label: Optional[str] = None) -> schemas.KitchenOrderOut:
    items = [
        schemas.KitchenOrderItemOut(
            id=i.id, menu_item_id=i.menu_item_id, name=i.name,
            unit_price=i.unit_price, quantity=i.quantity, notes=i.notes,
        ) for i in order.items
    ]
    total = sum(i.unit_price * i.quantity for i in items)
    return schemas.KitchenOrderOut(
        id=order.id, table_id=order.table_id, table_label=table_label, order_type=order.order_type,
        status=order.status, customer_name=order.customer_name, customer_phone=order.customer_phone,
        delivery_address=order.delivery_address, notes=order.notes, billed=bool(order.bill_id),
        items=items, total=total, created_at=order.created_at, updated_at=order.updated_at,
    )


def _get_order_or_404(db: Session, tenant_id: str, order_id: str) -> models.KitchenOrder:
    order = db.query(models.KitchenOrder).filter(
        models.KitchenOrder.id == order_id, models.KitchenOrder.tenant_id == tenant_id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    return order


@router.get("/orders", response_model=List[schemas.KitchenOrderOut])
def list_orders(order_type: Optional[str] = None, status: Optional[str] = None,
                 table_id: Optional[str] = None, db: Session = Depends(get_db),
                 user: models.User = Depends(_require)):
    """Endpoint condiviso da tre schermate: "Cucina" (status=in_attesa,in_preparazione,pronto),
    "Gestione ordini" (nessun filtro o filtro manuale) e la mappa tavoli (table_id).
    status accetta una lista separata da virgola per coprire più stati in una chiamata sola."""
    q = db.query(models.KitchenOrder).filter(models.KitchenOrder.tenant_id == user.tenant_id)
    if order_type:
        q = q.filter(models.KitchenOrder.order_type == order_type)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        q = q.filter(models.KitchenOrder.status.in_(statuses))
    if table_id:
        q = q.filter(models.KitchenOrder.table_id == table_id)
    orders = q.order_by(models.KitchenOrder.created_at.desc()).all()
    table_ids = {o.table_id for o in orders if o.table_id}
    tables = {t.id: t.label for t in db.query(models.RestaurantTable).filter(
        models.RestaurantTable.id.in_(table_ids)
    ).all()} if table_ids else {}
    return [_order_to_out(o, tables.get(o.table_id)) for o in orders]


@router.post("/orders", response_model=schemas.KitchenOrderOut)
def create_order(payload: schemas.KitchenOrderCreate, db: Session = Depends(get_db),
                  user: models.User = Depends(_require)):
    if payload.order_type not in ("tavolo", "asporto", "delivery"):
        raise HTTPException(status_code=400, detail="Tipo ordine non valido")
    table_label = None
    if payload.order_type == "tavolo":
        if not payload.table_id:
            raise HTTPException(status_code=400, detail="Indica il tavolo per un ordine al tavolo")
        table = db.query(models.RestaurantTable).filter(
            models.RestaurantTable.id == payload.table_id, models.RestaurantTable.tenant_id == user.tenant_id
        ).first()
        if not table:
            raise HTTPException(status_code=404, detail="Tavolo non trovato")
        table_label = table.label
    if not payload.items:
        raise HTTPException(status_code=400, detail="Aggiungi almeno un piatto alla comanda")

    order = models.KitchenOrder(
        tenant_id=user.tenant_id, table_id=payload.table_id if payload.order_type == "tavolo" else None,
        order_type=payload.order_type, customer_name=payload.customer_name,
        customer_phone=payload.customer_phone, delivery_address=payload.delivery_address, notes=payload.notes,
    )
    db.add(order)
    db.flush()

    for item_payload in payload.items:
        name = item_payload.name
        unit_price = 0.0
        if item_payload.menu_item_id:
            menu_item = db.query(models.MenuItem).filter(
                models.MenuItem.id == item_payload.menu_item_id, models.MenuItem.tenant_id == user.tenant_id
            ).first()
            if not menu_item:
                raise HTTPException(status_code=404, detail="Voce di menu non trovata")
            name = name or menu_item.name
            unit_price = menu_item.price
        if not name:
            raise HTTPException(status_code=400, detail="Ogni piatto deve avere un nome o una voce di menu collegata")
        db.add(models.KitchenOrderItem(
            order_id=order.id, menu_item_id=item_payload.menu_item_id, name=name,
            unit_price=unit_price, quantity=max(1, item_payload.quantity), notes=item_payload.notes,
        ))

    db.commit()
    db.refresh(order)
    return _order_to_out(order, table_label)


@router.patch("/orders/{order_id}/status", response_model=schemas.KitchenOrderOut)
def update_order_status(order_id: str, payload: schemas.KitchenOrderStatusUpdate, db: Session = Depends(get_db),
                         user: models.User = Depends(_require)):
    if payload.status not in _ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Stato ordine non valido")
    order = _get_order_or_404(db, user.tenant_id, order_id)
    order.status = payload.status
    db.commit()
    db.refresh(order)
    table = db.query(models.RestaurantTable).filter(models.RestaurantTable.id == order.table_id).first() if order.table_id else None
    return _order_to_out(order, table.label if table else None)


# ---------- Conto ----------
def _open_orders_for_table(db: Session, tenant_id: str, table_id: str) -> List[models.KitchenOrder]:
    return db.query(models.KitchenOrder).filter(
        models.KitchenOrder.tenant_id == tenant_id, models.KitchenOrder.table_id == table_id,
        models.KitchenOrder.bill_id.is_(None), models.KitchenOrder.status != "annullato",
    ).all()


@router.get("/tables/{table_id}/bill", response_model=schemas.BillPreviewOut)
def preview_table_bill(table_id: str, db: Session = Depends(get_db), user: models.User = Depends(_require)):
    table = db.query(models.RestaurantTable).filter(
        models.RestaurantTable.id == table_id, models.RestaurantTable.tenant_id == user.tenant_id
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Tavolo non trovato")
    orders = _open_orders_for_table(db, user.tenant_id, table_id)
    orders_out = [_order_to_out(o, table.label) for o in orders]
    subtotal = sum(o.total for o in orders_out)
    return schemas.BillPreviewOut(table_id=table.id, table_label=table.label, orders=orders_out, subtotal=subtotal)


def _close_bill(db: Session, tenant_id: str, table_id: Optional[str], orders: List[models.KitchenOrder],
                 payload: schemas.BillCloseRequest) -> models.Bill:
    if not orders:
        raise HTTPException(status_code=400, detail="Nessun ordine da fatturare")
    subtotal = sum(i.unit_price * i.quantity for o in orders for i in o.items)
    total = max(0.0, subtotal - payload.discount)
    bill = models.Bill(
        tenant_id=tenant_id, table_id=table_id, subtotal=subtotal, discount=payload.discount,
        total=total, payment_method=payload.payment_method, status="pagato",
        paid_at=datetime.utcnow(),
    )
    db.add(bill)
    db.flush()
    for o in orders:
        o.bill_id = bill.id
        o.status = "consegnato" if o.status != "annullato" else o.status
    db.commit()
    db.refresh(bill)
    return bill


def _bill_to_out(bill: models.Bill, table_label: Optional[str] = None) -> schemas.BillOut:
    return schemas.BillOut(
        id=bill.id, table_id=bill.table_id, table_label=table_label, subtotal=bill.subtotal,
        discount=bill.discount, total=bill.total, payment_method=bill.payment_method,
        status=bill.status, paid_at=bill.paid_at, created_at=bill.created_at,
    )


@router.post("/tables/{table_id}/bill/close", response_model=schemas.BillOut)
def close_table_bill(table_id: str, payload: schemas.BillCloseRequest, db: Session = Depends(get_db),
                      user: models.User = Depends(_require)):
    table = db.query(models.RestaurantTable).filter(
        models.RestaurantTable.id == table_id, models.RestaurantTable.tenant_id == user.tenant_id
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Tavolo non trovato")
    orders = _open_orders_for_table(db, user.tenant_id, table_id)
    bill = _close_bill(db, user.tenant_id, table_id, orders, payload)
    return _bill_to_out(bill, table.label)


@router.post("/orders/{order_id}/bill/close", response_model=schemas.BillOut)
def close_order_bill(order_id: str, payload: schemas.BillCloseRequest, db: Session = Depends(get_db),
                      user: models.User = Depends(_require)):
    """Fattura un singolo ordine (asporto/delivery, dove tipicamente si paga
    ordine per ordine e non c'è un tavolo su cui accumulare più comande)."""
    order = _get_order_or_404(db, user.tenant_id, order_id)
    if order.bill_id:
        raise HTTPException(status_code=400, detail="Ordine già fatturato")
    if order.status == "annullato":
        raise HTTPException(status_code=400, detail="Ordine annullato, non fatturabile")
    bill = _close_bill(db, user.tenant_id, None, [order], payload)
    return _bill_to_out(bill)


@router.get("/bills", response_model=List[schemas.BillOut])
def list_bills(db: Session = Depends(get_db), user: models.User = Depends(_require)):
    bills = db.query(models.Bill).filter(
        models.Bill.tenant_id == user.tenant_id
    ).order_by(models.Bill.created_at.desc()).limit(200).all()
    table_ids = {b.table_id for b in bills if b.table_id}
    tables = {t.id: t.label for t in db.query(models.RestaurantTable).filter(
        models.RestaurantTable.id.in_(table_ids)
    ).all()} if table_ids else {}
    return [_bill_to_out(b, tables.get(b.table_id)) for b in bills]
