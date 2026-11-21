"""AM Intelligence (đề cương mục 4.8): hỗ trợ nhân viên phụ trách theo dõi đơn vị/khách hàng.

- Danh mục đơn vị phụ trách kèm DTI, số dịch vụ đang dùng, doanh thu tháng
- Cơ hội phát triển dịch vụ = dịch vụ thuộc nhóm giải pháp được đề xuất mà đơn vị CHƯA sử dụng
- Gia hạn: dịch vụ sắp hết hạn (≤ 60 ngày) hoặc đã hết hạn
- Chăm sóc: dịch vụ đang dùng nhưng mức khai thác thấp (< 40%)
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DTIScore, Recommendation, ServiceCatalog, Unit, UnitService, User
from ..security import require, scoped_unit_ids
from .common import apply_scope, get_period

router = APIRouter(prefix="/api/am", tags=["AM Intelligence"])


@router.get("/portfolio")
def portfolio(period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("am.view"))):
    p = get_period(db, period)
    scope = scoped_unit_ids(db, user)
    units = db.execute(apply_scope(select(Unit, DTIScore).outerjoin(
        DTIScore, (DTIScore.unit_id == Unit.id) & (DTIScore.period_id == p.id)), Unit.id, scope)
        .order_by(Unit.name)).all()
    ids = [u.id for u, _ in units]
    svcs = db.scalars(select(UnitService).where(UnitService.unit_id.in_(ids or [-1]))).all()
    catalog = {s.code: s for s in db.scalars(select(ServiceCatalog))}
    recs = db.scalars(select(Recommendation).where(Recommendation.unit_id.in_(ids or [-1]), Recommendation.period_id == p.id)).all()
    today = date.today()

    by_unit: dict[int, list[UnitService]] = {}
    for s in svcs:
        by_unit.setdefault(s.unit_id, []).append(s)
    names = {u.id: u.name for u, _ in units}

    opportunities, renewals, care = [], [], []
    for r in recs:
        for code in r.missing_services:
            sv = catalog.get(code)
            if not sv:
                continue
            opportunities.append({"unit_id": r.unit_id, "unit_name": names[r.unit_id], "service_code": code,
                                  "service_name": sv.name, "solution": r.solution.name, "priority_level": r.priority_level,
                                  "priority_score": r.priority_score, "est_monthly": float(sv.monthly_price), "reason": r.reason})
    # gộp trùng (cùng đơn vị – dịch vụ), giữ ưu tiên cao nhất
    best = {}
    for o in opportunities:
        k = (o["unit_id"], o["service_code"])
        if k not in best or o["priority_score"] > best[k]["priority_score"]:
            best[k] = o
    opportunities = sorted(best.values(), key=lambda x: -x["priority_score"])

    for s in svcs:
        if s.status in ("dang_dung", "dung_thu", "het_han") and s.end_date and s.end_date <= today + timedelta(days=60):
            renewals.append({"unit_id": s.unit_id, "unit_name": names[s.unit_id], "service_name": s.service.name,
                             "status": s.status, "end_date": s.end_date, "days_left": (s.end_date - today).days,
                             "monthly_fee": float(s.monthly_fee or 0)})
        if s.status == "dang_dung" and s.usage_level < 40:
            care.append({"unit_id": s.unit_id, "unit_name": names[s.unit_id], "service_name": s.service.name,
                         "usage_level": s.usage_level})
    renewals.sort(key=lambda x: x["days_left"])
    care.sort(key=lambda x: x["usage_level"])

    items = []
    for u, d in units:
        us = by_unit.get(u.id, [])
        active = [s for s in us if s.status in ("dang_dung", "dung_thu")]
        items.append({"unit_id": u.id, "name": u.name, "unit_type": u.unit_type, "region": u.region.name,
                      "dti": d.score if d else None, "level": d.level if d else None,
                      "active_services": len(active), "monthly_revenue": sum(float(s.monthly_fee or 0) for s in active),
                      "avg_usage": round(sum(s.usage_level for s in active) / len(active), 1) if active else 0,
                      "opportunities": sum(1 for o in opportunities if o["unit_id"] == u.id)})
    # tỷ lệ phủ dịch vụ
    coverage = []
    for code, sv in catalog.items():
        eligible = [u for u, _ in units if u.unit_type in sv.unit_types]
        if not eligible:
            continue
        using = sum(1 for s in svcs if s.service.code == code and s.status in ("dang_dung", "dung_thu"))
        coverage.append({"code": code, "name": sv.name, "eligible": len(eligible), "using": using,
                         "rate": round(using * 100 / len(eligible), 1)})
    coverage.sort(key=lambda x: x["rate"])
    return {
        "period": p.code,
        "summary": {"units": len(units), "monthly_revenue": sum(i["monthly_revenue"] for i in items),
                    "opportunities": len(opportunities),
                    "potential_monthly": sum(o["est_monthly"] for o in opportunities),
                    "renewals": len(renewals), "low_usage": len(care)},
        "units": items, "opportunities": opportunities[:100], "renewals": renewals, "care": care[:50], "coverage": coverage,
    }



# ---------------- kế hoạch chăm sóc đơn vị (đề cương 3.3: "hỗ trợ xây dựng kế hoạch chăm sóc đơn vị")
from datetime import date as _date  # noqa: E402

from fastapi import HTTPException, Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from ..models import CarePlan  # noqa: E402
from ..security import audit, ensure_unit_access  # noqa: E402

ACTIVITIES = {"tu_van": "Tư vấn giải pháp", "tap_huan": "Tập huấn, hướng dẫn sử dụng", "gia_han": "Gia hạn dịch vụ",
              "trien_khai": "Triển khai dịch vụ mới", "khao_sat": "Khảo sát nhu cầu", "ho_tro": "Hỗ trợ kỹ thuật"}


def _cp_out(c: CarePlan, db) -> dict:
    return {"id": c.id, "unit_id": c.unit_id, "unit_name": db.get(Unit, c.unit_id).name, "activity": c.activity,
            "activity_name": ACTIVITIES.get(c.activity, c.activity), "title": c.title, "service_code": c.service_code,
            "planned_date": c.planned_date, "status": c.status, "note": c.note, "result": c.result,
            "overdue": c.status == "ke_hoach" and c.planned_date < _date.today()}


@router.get("/care-plans")
def care_plans(unit_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require("am.view"))):
    stmt = select(CarePlan)
    scope = scoped_unit_ids(db, user)
    if scope is not None:
        stmt = stmt.where(CarePlan.unit_id.in_(scope or [-1]))
    if unit_id:
        stmt = stmt.where(CarePlan.unit_id == unit_id)
    return {"activities": ACTIVITIES, "items": [_cp_out(c, db) for c in db.scalars(stmt.order_by(CarePlan.planned_date))]}


class CareIn(BaseModel):
    unit_id: int
    activity: str
    title: str
    service_code: str | None = None
    planned_date: _date
    status: str = "ke_hoach"
    note: str | None = None
    result: str | None = None


@router.post("/care-plans")
def create_care(body: CareIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("am.view"))):
    ensure_unit_access(db, user, body.unit_id)
    if body.activity not in ACTIVITIES:
        raise HTTPException(400, "Loại hoạt động không hợp lệ")
    c = CarePlan(**body.model_dump(), am_user_id=user.id)
    db.add(c)
    audit(db, user, "create_care_plan", "care_plan", None, body.model_dump(mode="json"), request)
    db.commit()
    return _cp_out(c, db)


@router.put("/care-plans/{cid}")
def update_care(cid: int, body: CareIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("am.view"))):
    c = db.get(CarePlan, cid)
    if not c:
        raise HTTPException(404)
    ensure_unit_access(db, user, c.unit_id)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return _cp_out(c, db)


@router.delete("/care-plans/{cid}")
def delete_care(cid: int, db: Session = Depends(get_db), user: User = Depends(require("am.view"))):
    c = db.get(CarePlan, cid)
    if not c:
        raise HTTPException(404)
    ensure_unit_access(db, user, c.unit_id)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/care-plans/suggest")
def suggest_care(unit_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require("am.view"))):
    """Sinh kế hoạch chăm sóc gợi ý cho một đơn vị từ dữ liệu: gia hạn, khai thác thấp, cơ hội dịch vụ từ đề xuất."""
    ensure_unit_access(db, user, unit_id)
    pf = portfolio(None, db, user)
    today = _date.today()
    have = {(c.activity, c.service_code) for c in db.scalars(select(CarePlan).where(CarePlan.unit_id == unit_id, CarePlan.status == "ke_hoach"))}
    svc_code = {s.name: s.code for s in db.scalars(select(ServiceCatalog))}
    new = []
    for r in pf["renewals"]:
        if r["unit_id"] == unit_id:
            new.append(("gia_han", f"Gia hạn {r['service_name']}", svc_code.get(r["service_name"]),
                        max(today, r["end_date"] - timedelta(days=15)) if r["days_left"] > 15 else today))
    for c in pf["care"]:
        if c["unit_id"] == unit_id:
            new.append(("tap_huan", f"Tập huấn khai thác {c['service_name']} (đang dùng {c['usage_level']}%)", svc_code.get(c["service_name"]), today + timedelta(days=14)))
    for o in [o for o in pf["opportunities"] if o["unit_id"] == unit_id][:4]:
        new.append(("tu_van", f"Tư vấn {o['service_name']} – {o['solution']}", o["service_code"], today + timedelta(days=21)))
    created = 0
    for act, title, code, d in new:
        if (act, code) in have:
            continue
        db.add(CarePlan(unit_id=unit_id, am_user_id=user.id, activity=act, title=title, service_code=code, planned_date=d,
                        note="Gợi ý tự động từ dữ liệu dịch vụ và đề xuất CĐS"))
        have.add((act, code))
        created += 1
    audit(db, user, "suggest_care_plan", "unit", unit_id, {"created": created}, request)
    db.commit()
    return {"created": created}
