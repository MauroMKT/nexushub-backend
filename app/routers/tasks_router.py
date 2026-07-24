"""Router M3 - Reminder & Task."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

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
    task = models.Task(tenant_id=user.tenant_id, assigned_user_id=user.id, **payload.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
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
