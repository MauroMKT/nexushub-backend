"""
Motore di esecuzione reale per le regole di automazione (M5), esteso per creare
task "intelligenti" in automatico in base a eventi del CRM.

Una AutomationRule ha:
  - trigger_type: "new_client" | "stage_change" | "appointment_created" | "task_overdue"
  - conditions: JSON, es. {"stage_name": "Trattativa"} (opzionale, per stage_change)
  - actions: JSON, lista di azioni. Azione supportata oggi:
      {"type": "create_task", "title_template": "Richiama {client_name} entro {due_in_days} giorni",
       "due_in_days": 3, "assign_to": "owner"}
      {"type": "notify_admins", "title": "Nuovo cliente acquisito", "body_template": "{client_name} è stato aggiunto al CRM"}

Le regole sono definite dal tenant in Impostazioni > Automazioni (pagina già esistente,
router `automations_router.py`). Questo modulo viene richiamato dai router che generano
gli eventi (clients_router, pipeline_router, appointments_router, tasks_router) subito
dopo il commit dell'entità principale.
"""
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import models
from .notifications import notify_tenant_admins


def run_automation(db: Session, tenant_id: str, trigger_type: str, context: dict) -> list:
    """Valuta tutte le regole attive del tenant per questo trigger_type ed esegue le azioni.
    Ritorna la lista delle azioni effettivamente eseguite (per debug/log)."""
    rules = db.query(models.AutomationRule).filter(
        models.AutomationRule.tenant_id == tenant_id,
        models.AutomationRule.trigger_type == trigger_type,
        models.AutomationRule.is_active == True,  # noqa: E712
    ).all()

    executed = []
    for rule in rules:
        try:
            conditions = json.loads(rule.conditions or "{}")
        except (TypeError, ValueError):
            conditions = {}
        if not _conditions_match(conditions, context):
            continue

        try:
            actions = json.loads(rule.actions or "[]")
        except (TypeError, ValueError):
            actions = []

        for action in actions:
            result = _execute_action(db, tenant_id, action, context)
            if result:
                executed.append({"rule_name": rule.name, **result})

    return executed


def _conditions_match(conditions: dict, context: dict) -> bool:
    """Confronto semplice chiave=valore: tutte le condizioni definite devono combaciare
    con il contesto dell'evento (es. {"stage_name": "Trattativa"})."""
    for key, expected in conditions.items():
        if str(context.get(key, "")) != str(expected):
            return False
    return True


def _execute_action(db: Session, tenant_id: str, action: dict, context: dict) -> dict | None:
    action_type = action.get("type")

    if action_type == "create_task":
        due_in_days = int(action.get("due_in_days", 3))
        title = _render_template(action.get("title_template", "Nuovo task automatico"), context)
        assigned_user_id = None
        if action.get("assign_to") == "owner":
            assigned_user_id = context.get("owner_user_id")

        task = models.Task(
            tenant_id=tenant_id,
            assigned_user_id=assigned_user_id,
            client_id=context.get("client_id"),
            title=title,
            due_date=datetime.utcnow() + timedelta(days=due_in_days),
            done=False,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return {"action": "create_task", "task_id": task.id, "title": task.title}

    if action_type == "notify_admins":
        title = _render_template(action.get("title", "Notifica automazione"), context)
        body = _render_template(action.get("body_template", ""), context)
        notify_tenant_admins(db, tenant_id, title, body, related_type=context.get("related_type"),
                             related_id=context.get("related_id"))
        return {"action": "notify_admins", "title": title}

    return None


def _render_template(template: str, context: dict) -> str:
    try:
        return template.format(**context)
    except (KeyError, IndexError):
        return template
