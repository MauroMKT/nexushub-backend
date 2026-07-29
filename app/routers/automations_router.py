"""Router M5 - Motore di Automazioni & Blueprint."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/automations", tags=["Automazioni & Blueprint"])


# --- Automation Rules ---
@router.get("/rules", response_model=List[schemas.AutomationRuleOut])
def list_rules(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.AutomationRule).filter(
        models.AutomationRule.tenant_id == user.tenant_id
    ).all()


@router.post("/rules", response_model=schemas.AutomationRuleOut)
def create_rule(payload: schemas.AutomationRuleCreate, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    rule = models.AutomationRule(tenant_id=user.tenant_id, **payload.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=schemas.AutomationRuleOut)
def update_rule(rule_id: str, payload: schemas.AutomationRuleCreate, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id, models.AutomationRule.tenant_id == user.tenant_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regola di automazione non trovata")
    for field, value in payload.dict().items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id, models.AutomationRule.tenant_id == user.tenant_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regola di automazione non trovata")
    db.delete(rule)
    db.commit()
    return {"ok": True}


# --- Blueprints ---
@router.get("/blueprints", response_model=List[schemas.BlueprintOut])
def list_blueprints(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Blueprint).filter(
        models.Blueprint.tenant_id == user.tenant_id
    ).all()


@router.post("/blueprints", response_model=schemas.BlueprintOut)
def create_blueprint(payload: schemas.BlueprintCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    bp = models.Blueprint(tenant_id=user.tenant_id, **payload.dict())
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return bp


@router.put("/blueprints/{bp_id}", response_model=schemas.BlueprintOut)
def update_blueprint(bp_id: str, payload: schemas.BlueprintCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    bp = db.query(models.Blueprint).filter(
        models.Blueprint.id == bp_id, models.Blueprint.tenant_id == user.tenant_id
    ).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint non trovato")
    for field, value in payload.dict().items():
        setattr(bp, field, value)
    db.commit()
    db.refresh(bp)
    return bp


@router.delete("/blueprints/{bp_id}")
def delete_blueprint(bp_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    bp = db.query(models.Blueprint).filter(
        models.Blueprint.id == bp_id, models.Blueprint.tenant_id == user.tenant_id
    ).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint non trovato")
    db.delete(bp)
    db.commit()
    return {"ok": True}


# --- Simulation trigger ---
@router.post("/trigger")
def trigger_event(event_type: str, entity_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    """Simula l'attivazione di un trigger per testare il motore di automazione."""
    # Trova le regole attive per questo tenant ed evento
    rules = db.query(models.AutomationRule).filter(
        models.AutomationRule.tenant_id == user.tenant_id,
        models.AutomationRule.trigger_type == event_type,
        models.AutomationRule.is_active == True
    ).all()
    
    triggered_actions = []
    
    # Per ciascuna regola, esegue le azioni (simulazione)
    for rule in rules:
        # Nel mondo reale, interpreteremmo rule.actions ed eseguiamo.
        # Qui simuliamo l'inserimento o la logica.
        triggered_actions.append({
            "rule_name": rule.name,
            "status": "executed_simulated",
            "actions": rule.actions
        })
        
    return {
        "event_type": event_type,
        "entity_id": entity_id,
        "matched_rules_count": len(rules),
        "triggered_actions": triggered_actions
    }
