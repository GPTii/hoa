from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Period


def get_period(db: Session, code: str | None) -> Period:
    if code:
        p = db.scalar(select(Period).where(Period.code == code))
    else:
        p = db.scalar(select(Period).where(Period.is_current)) or db.scalar(select(Period).order_by(Period.start_date.desc()))
    if not p:
        raise HTTPException(404, "Không tìm thấy kỳ đánh giá")
    return p


def apply_scope(stmt, column, ids: list[int] | None):
    """Thêm điều kiện phạm vi dữ liệu theo phân quyền vào câu truy vấn."""
    if ids is None:
        return stmt
    return stmt.where(column.in_(ids or [-1]))
