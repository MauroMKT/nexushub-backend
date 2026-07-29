"""Router abbonamenti (Fase 7) - piani Free/Premium/Enterprise con pagamenti
reali via Stripe. Finché STRIPE_SECRET_KEY non è impostata sul backend,
checkout/portal restituiscono un errore chiaro invece di fallire in modo
oscuro (stesso pattern usato per l'integrazione Google Calendar).

Prezzi indicativi: modificabili qui in PLANS senza toccare nessun'altra parte
del codice. Il piano Enterprise è pensato per essere spesso "su richiesta"
(contatto commerciale) più che self-service, ma il checkout self-service resta
disponibile se Mauro configura un price Stripe anche per quel piano."""
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_admin
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/billing", tags=["Abbonamenti"])

PLANS = {
    "free": {
        "name": "Free", "price_monthly": 0, "price_annual": 0,
        "max_users": 1, "max_clients": 50,
        "features": ["crm_core", "calendar", "tasks", "contacts"],
    },
    "premium": {
        "name": "Premium", "price_monthly": 39, "price_annual": 390,
        "max_users": 10, "max_clients": None,
        "features": ["crm_core", "calendar", "tasks", "contacts", "whatsapp",
                     "email_marketing", "automations", "white_label", "notifications"],
    },
    "enterprise": {
        "name": "Enterprise", "price_monthly": 99, "price_annual": 990,
        "max_users": None, "max_clients": None,
        "features": ["crm_core", "calendar", "tasks", "contacts", "whatsapp",
                     "email_marketing", "automations", "white_label", "notifications",
                     "client_portal", "priority_support"],
    },
}


def _price_id_for(plan: str, cycle: str) -> str:
    mapping = {
        ("premium", "monthly"): settings.stripe_price_premium_monthly,
        ("premium", "annual"): settings.stripe_price_premium_annual,
        ("enterprise", "monthly"): settings.stripe_price_enterprise_monthly,
        ("enterprise", "annual"): settings.stripe_price_enterprise_annual,
    }
    return mapping.get((plan, cycle), "")


@router.get("/plans", response_model=List[schemas.BillingPlanOut])
def list_plans():
    return [schemas.BillingPlanOut(id=pid, **data) for pid, data in PLANS.items()]


@router.get("/status", response_model=schemas.BillingStatus)
def billing_status(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
    return schemas.BillingStatus(
        configured=bool(settings.stripe_secret_key),
        plan=tenant.plan,
        billing_cycle=tenant.billing_cycle,
        subscription_status=tenant.subscription_status,
        stripe_connected=bool(tenant.stripe_customer_id),
    )


@router.post("/checkout", response_model=schemas.CheckoutOut)
def create_checkout(payload: schemas.CheckoutRequest, db: Session = Depends(get_db),
                     admin: models.User = Depends(require_admin)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=400, detail="I pagamenti non sono ancora configurati: serve un account Stripe collegato al backend.")
    if payload.plan not in ("premium", "enterprise"):
        raise HTTPException(status_code=400, detail="Piano non valido per il checkout")
    if payload.billing_cycle not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="Ciclo di fatturazione non valido")

    price_id = _price_id_for(payload.plan, payload.billing_cycle)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Nessun price Stripe configurato per {payload.plan}/{payload.billing_cycle}")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    tenant = db.query(models.Tenant).filter(models.Tenant.id == admin.tenant_id).first()
    customer_id = tenant.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=admin.email, name=tenant.name, metadata={"tenant_id": tenant.id})
        customer_id = customer["id"]
        tenant.stripe_customer_id = customer_id
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/settings?billing=success",
        cancel_url=f"{settings.frontend_url}/settings?billing=cancel",
        metadata={"tenant_id": tenant.id, "plan": payload.plan, "billing_cycle": payload.billing_cycle},
    )
    return schemas.CheckoutOut(checkout_url=session["url"])


@router.post("/portal", response_model=schemas.BillingPortalOut)
def create_billing_portal(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=400, detail="I pagamenti non sono ancora configurati.")
    tenant = db.query(models.Tenant).filter(models.Tenant.id == admin.tenant_id).first()
    if not tenant.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nessun abbonamento attivo per questa azienda")

    import stripe
    stripe.api_key = settings.stripe_secret_key
    portal = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=f"{settings.frontend_url}/settings",
    )
    return schemas.BillingPortalOut(portal_url=portal["url"])


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Riceve gli eventi Stripe e aggiorna il piano/stato del tenant corrispondente.
    Va configurato come endpoint webhook nella dashboard Stripe una volta pronti."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=400, detail="Stripe non configurato")

    import stripe
    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        if settings.stripe_webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
        else:
            event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook non valido")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type in ("checkout.session.completed", "customer.subscription.updated", "customer.subscription.created"):
        metadata = data_object.get("metadata", {}) or {}
        tenant_id = metadata.get("tenant_id")
        tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first() if tenant_id else None
        if tenant:
            if metadata.get("plan"):
                tenant.plan = metadata["plan"]
            if metadata.get("billing_cycle"):
                tenant.billing_cycle = metadata["billing_cycle"]
            subscription_id = data_object.get("subscription") or data_object.get("id")
            if subscription_id:
                tenant.stripe_subscription_id = subscription_id
            status_value = data_object.get("status")
            if status_value:
                tenant.subscription_status = status_value
            db.commit()
    elif event_type == "customer.subscription.deleted":
        subscription_id = data_object.get("id")
        tenant = db.query(models.Tenant).filter(models.Tenant.stripe_subscription_id == subscription_id).first()
        if tenant:
            tenant.plan = "free"
            tenant.subscription_status = "canceled"
            db.commit()

    return {"received": True}
