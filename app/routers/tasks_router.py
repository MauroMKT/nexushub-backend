"""Router M3 - Reminder & Task."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..notifications import notify_user

router = APIRouter(prefix="/tasks", tags=["Reminder & Task"])


@router.get("", response_model=List[schemas.TaskOut])
def list_tasks(done: bool = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Task).filter(models.Task.tenant_id == user.tenant_id)
    if done is not None:
        q = q.filter(models.Task.done == done)
    return q.order_by(models.Task.due_date).all()


@router.post("", response_model=schemas.TaskOut)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    data = payload.dict()
    assigned_user_id = data.pop("assigned_user_id", None) or user.id
    task = models.Task(tenant_id=user.tenant_id, assigned_user_id=assigned_user_id, **data)
    db.add(task)
    db.commit()
    db.refresh(task)

    if assigned_user_id != user.id:
        assignee = db.query(models.User).filter(
            models.User.id == assigned_user_id, models.User.tenant_id == user.tenant_id
        ).first()
        if assignee:
            notify_user(db, assignee, "Nuovo task assegnato", f'{user.full_name} ti ha assegnato: "{task.title}"',
                        related_type="task", related_id=task.id)

    return task


@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: str, payload: schemas.TaskUpdate, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.tenant_id == user.tenant_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.tenant_id == user.tenant_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")
    db.delete(task)
    db.commit()
    return {"ok": True}
