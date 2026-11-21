"""Thông báo / nhắc việc của người dùng (chuông trên thanh tiêu đề)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notification, User
from ..security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Thông báo"])


@router.get("")
def my_notifications(limit: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.is_read, Notification.id.desc()).limit(limit)).all()
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, ~Notification.is_read))
    return {"unread": unread, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "task_id": n.task_id,
                                         "is_read": n.is_read, "created_at": n.created_at} for n in rows]}


@router.post("/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.id == nid, Notification.user_id == user.id).values(is_read=True))
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    db.commit()
    return {"ok": True}
