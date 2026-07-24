"""Router Dashboard base (KPI trasversali, anticipo del modulo M10)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tenant_id = user.tenant_id
    now = datetime.utcnow()
    week_end = now + timedelta(days=7)

    total_clients = db.query(func.count(models.Client.id)).filter(
        models.Client.tenant_id == tenant_id
    ).scalar() or 0

    appointments_this_week = db.query(func.count(models.Appointment.id)).filter(
        models.Appointment.tenant_id == tenant_id,
        models.Appointment.start_time >= now,
        models.Appointment.start_time <= week_end,
    ).scalar() or 0

    tasks_due = db.query(func.count(models.Task.id)).filter(
        models.Task.tenant_id == tenant_id,
        models.Task.done.is_(False),
    ).scalar() or 0

    open_deals = db.query(func.count(models.Deal.id)).filter(
        models.Deal.tenant_id == tenant_id
    ).scalar() or 0

    pipeline_value = db.query(func.coalesce(func.sum(models.Deal.value), 0.0)).filter(
        models.Deal.tenant_id == tenant_id
    ).scalar() or 0.0

    return schemas.DashboardSummary(
        total_clients=total_clients,
        appointments_this_week=appointments_this_week,
        tasks_due=tasks_due,
        open_deals=open_deals,
        pipeline_value=pipeline_value,
    )
