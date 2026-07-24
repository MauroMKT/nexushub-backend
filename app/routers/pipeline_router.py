"""Router M1 - Pipeline vendite kanban (fasi e trattative/deal)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/pipeline", tags=["CRM Core - Pipeline"])


@router.get("/stages", response_model=List[schemas.PipelineStageOut])
def list_stages(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.PipelineStage).filter(
        models.PipelineStage.tenant_id == user.tenant_id
    ).order_by(models.PipelineStage.order).all()


@router.get("/deals", response_model=List[schemas.DealOut])
def list_deals(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Deal).filter(models.Deal.tenant_id == user.tenant_id).all()


@router.post("/deals", response_model=schemas.DealOut)
def create_deal(payload: schemas.DealCreate, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    deal = models.Deal(tenant_id=user.tenant_id, **payload.dict())
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


@router.patch("/deals/{deal_id}/move", response_model=schemas.DealOut)
def move_deal(deal_id: str, payload: schemas.DealMove, db: Session = Depends(get_db),
              user: models.User = Depends(get_current_user)):
    """Sposta una trattativa lungo la pipeline kanban (drag & drop lato frontend)."""
    deal = db.query(models.Deal).filter(
        models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id
    ).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Trattativa non trovata")
    deal.stage_id = payload.stage_id
    db.commit()
    db.refresh(deal)
    return deal
