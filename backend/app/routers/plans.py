"""Hỗ trợ XÂY DỰNG KẾ HOẠCH cải thiện chuyển đổi số (đề cương mục 4.7).

Đánh giá hiện trạng → xác định vấn đề → mức ưu tiên → đề xuất nhóm giải pháp → **lập kế hoạch**:
người quản lý chọn các nhóm giải pháp được đề xuất → hệ thống sinh các hạng mục (đơn vị, hành động, thời hạn theo thời
lượng của giải pháp, mức chi phí, mức ưu tiên, điểm hiện trạng làm mốc) → điều chỉnh, ban hành, theo dõi tiến độ.
Hệ thống HỖ TRỢ, quyết định cuối cùng vẫn thuộc người quản lý.
"""
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DTIScore, ImprovementPlan, PlanItem, Recommendation, Region, Unit, User
from ..security import audit, perms_of, require, scoped_unit_ids
from .common import get_period

router = APIRouter(prefix="/api/plans", tags=["Kế hoạch cải thiện CĐS"])
STATUS = {"chua_lam": "Chưa thực hiện", "dang_lam": "Đang thực hiện", "hoan_thanh": "Hoàn thành"}
PLAN_STATUS = {"du_thao": "Dự thảo", "ban_hanh": "Đã ban hành", "hoan_thanh": "Đã hoàn thành"}


def _can_see(db, user, plan: ImprovementPlan) -> bool:
    ids = scoped_unit_ids(db, user)
    return ids is None or plan.owner_unit_id in ids or any(i.unit_id in ids for i in plan.items)


def plan_out(p: ImprovementPlan, db: Session, full=False) -> dict:
    items = p.items
    done = sum(1 for i in items if i.status == "hoan_thanh")
    d = {"id": p.id, "title": p.title, "scope": p.scope, "status": p.status, "status_name": PLAN_STATUS[p.status],
         "unit_name": db.get(Unit, p.unit_id).name if p.unit_id else None,
         "region_name": db.get(Region, p.region_id).name if p.region_id else None,
         "owner": db.get(Unit, p.owner_unit_id).name if p.owner_unit_id else None,
         "period": p.period_id, "created_at": p.created_at, "note": p.note, "item_count": len(items), "done_count": done,
         "progress": round(sum(i.progress for i in items) / len(items)) if items else 0,
         "units": len({i.unit_id for i in items})}
    if full:
        d["items"] = [{"id": i.id, "unit_id": i.unit_id, "unit_name": i.unit.name, "solution": i.solution.name if i.solution else None,
                       "pillar": i.solution.pillar.name if i.solution else None, "action": i.action, "responsible": i.responsible,
                       "start_date": i.start_date, "end_date": i.end_date, "priority": i.priority, "cost_level": i.cost_level,
                       "status": i.status, "status_name": STATUS[i.status], "progress": i.progress,
                       "baseline_score": i.baseline_score,
                       "overdue": i.status != "hoan_thanh" and i.end_date is not None and i.end_date < date.today()} for i in p.items]
    return d


@router.get("")
def list_plans(db: Session = Depends(get_db), user: User = Depends(require("plan.view"))):
    plans = db.scalars(select(ImprovementPlan).order_by(ImprovementPlan.id.desc())).all()
    return [plan_out(p, db) for p in plans if _can_see(db, user, p)]


class PlanIn(BaseModel):
    title: str
    period: str | None = None
    unit_id: int | None = None          # kế hoạch cho 1 đơn vị
    region_id: int | None = None        # kế hoạch cho cả địa bàn (mọi đơn vị trong phạm vi)
    solution_ids: list[int]             # các nhóm giải pháp được chọn từ đề xuất
    start_date: date | None = None
    only_high: bool = False             # chỉ lấy đơn vị có mức ưu tiên cao


@router.post("")
def create_plan(body: PlanIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("plan.manage"))):
    p = get_period(db, body.period)
    scope = scoped_unit_ids(db, user)
    stmt = select(Recommendation).where(Recommendation.period_id == p.id, Recommendation.solution_group_id.in_(body.solution_ids or [-1]))
    if body.unit_id:
        stmt = stmt.where(Recommendation.unit_id == body.unit_id)
    elif body.region_id:
        stmt = stmt.where(Recommendation.unit_id.in_(select(Unit.id).where(Unit.region_id == body.region_id)))
    if scope is not None:
        stmt = stmt.where(Recommendation.unit_id.in_(scope or [-1]))
    if body.only_high:
        stmt = stmt.where(Recommendation.priority_level == "cao")
    recs = db.scalars(stmt.order_by(Recommendation.priority_score.desc())).all()
    if not recs:
        raise HTTPException(400, "Không có đề xuất nào khớp lựa chọn trong phạm vi của bạn")
    start = body.start_date or date.today()
    plan = ImprovementPlan(title=body.title, scope="unit" if body.unit_id else "region" if body.region_id else "tinh",
                           unit_id=body.unit_id, region_id=body.region_id, period_id=p.id, owner_unit_id=user.unit_id,
                           created_by=user.id)
    db.add(plan)
    db.flush()
    for r in recs:
        g = r.solution
        u = db.get(Unit, r.unit_id)
        db.add(PlanItem(plan_id=plan.id, unit_id=r.unit_id, solution_group_id=g.id,
                        action=g.actions or g.name, responsible=f"Người đứng đầu {u.name}",
                        start_date=start, end_date=start + timedelta(days=30 * (g.duration_months or 3)),
                        priority=r.priority_level, cost_level=g.cost_level, baseline_score=round(100 - r.priority_score, 1)))
    audit(db, user, "create_plan", "plan", plan.id, {"title": body.title, "items": len(recs)}, request)
    db.commit()
    db.refresh(plan)
    return plan_out(plan, db, full=True)


@router.get("/{pid}")
def get_plan(pid: int, db: Session = Depends(get_db), user: User = Depends(require("plan.view"))):
    p = db.get(ImprovementPlan, pid)
    if not p or not _can_see(db, user, p):
        raise HTTPException(404)
    d = plan_out(p, db, full=True)
    # đánh giá hiệu quả: DTI hiện tại của các đơn vị trong kế hoạch
    cur = get_period(db, None)
    d["dti_now"] = {uid: s for uid, s in db.execute(select(DTIScore.unit_id, DTIScore.score).where(
        DTIScore.period_id == cur.id, DTIScore.unit_id.in_([i.unit_id for i in p.items] or [-1])))}
    d["can_edit"] = "plan.manage" in perms_of(user) and (p.created_by == user.id or user.unit_id == p.owner_unit_id)
    return d


class PlanUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    note: str | None = None


@router.put("/{pid}")
def update_plan(pid: int, body: PlanUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require("plan.manage"))):
    p = db.get(ImprovementPlan, pid)
    if not p or not _can_see(db, user, p):
        raise HTTPException(404)
    if body.status and body.status not in PLAN_STATUS:
        raise HTTPException(400, "Trạng thái không hợp lệ")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    audit(db, user, "update_plan", "plan", pid, body.model_dump(exclude_none=True), request)
    db.commit()
    return plan_out(p, db)


class ItemUpdate(BaseModel):
    action: str | None = None
    responsible: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    progress: int | None = None


@router.put("/items/{iid}")
def update_item(iid: int, body: ItemUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require("plan.view"))):
    """Người lập kế hoạch sửa mọi hạng mục; đơn vị được giao chỉ cập nhật tiến độ hạng mục của mình."""
    it = db.get(PlanItem, iid)
    if not it:
        raise HTTPException(404)
    plan = db.get(ImprovementPlan, it.plan_id)
    owner = "plan.manage" in perms_of(user) and (plan.created_by == user.id or user.unit_id == plan.owner_unit_id)
    if not owner:
        if user.unit_id != it.unit_id or set(body.model_dump(exclude_none=True)) - {"status", "progress"}:
            raise HTTPException(403, "Chỉ người lập kế hoạch sửa nội dung; đơn vị được giao chỉ cập nhật tiến độ")
    if body.status and body.status not in STATUS:
        raise HTTPException(400, "Trạng thái không hợp lệ")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(it, k, v)
    if body.status == "hoan_thanh":
        it.progress = 100
    if body.progress is not None:
        it.progress = max(0, min(100, body.progress))
        if it.progress == 100:
            it.status = "hoan_thanh"
        elif it.progress > 0 and it.status == "chua_lam":
            it.status = "dang_lam"
    audit(db, user, "update_plan_item", "plan_item", iid, body.model_dump(exclude_none=True, mode="json"), request)
    db.commit()
    return {"ok": True}


@router.delete("/{pid}")
def delete_plan(pid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require("plan.manage"))):
    p = db.get(ImprovementPlan, pid)
    if not p or not (p.created_by == user.id or user.unit_id == p.owner_unit_id):
        raise HTTPException(404)
    if p.status != "du_thao":
        raise HTTPException(400, "Chỉ xóa được kế hoạch ở trạng thái dự thảo")
    db.delete(p)
    audit(db, user, "delete_plan", "plan", pid, request=request)
    db.commit()
    return {"ok": True}


@router.get("/{pid}/export.xlsx")
def export_plan(pid: int, db: Session = Depends(get_db), user: User = Depends(require("plan.view"))):
    from .admin_ops import xlsx_response
    d = get_plan(pid, db, user)
    head = pd.DataFrame({"Thông tin": [f"KẾ HOẠCH: {d['title']}", f"Đơn vị lập: {d['owner'] or ''}", f"Trạng thái: {d['status_name']}",
                                       f"Số hạng mục: {d['item_count']} · Đơn vị tham gia: {d['units']}", f"Tiến độ chung: {d['progress']}%"]})
    items = pd.DataFrame([{"STT": n, "Đơn vị": i["unit_name"], "Nhóm giải pháp": i["solution"], "Trụ cột": i["pillar"],
                           "Nội dung thực hiện": i["action"], "Người/đơn vị chịu trách nhiệm": i["responsible"],
                           "Bắt đầu": i["start_date"], "Hoàn thành": i["end_date"], "Ưu tiên": i["priority"],
                           "Chi phí": i["cost_level"], "Trạng thái": i["status_name"], "Tiến độ (%)": i["progress"],
                           "Điểm hiện trạng (mốc)": i["baseline_score"], "DTI hiện tại": d["dti_now"].get(i["unit_id"])}
                          for n, i in enumerate(d["items"], start=1)])
    return xlsx_response({"thong_tin": head, "hang_muc": items}, f"ke_hoach_{pid}.xlsx")
