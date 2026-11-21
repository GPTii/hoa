from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Criterion, CriterionScore, DTIScore, Period, Pillar, PillarScore, Recommendation, Region, ServiceCatalog,
    SolutionGroup, Unit, UnitCluster, UnitInfra, UnitService, User,
)
from ..security import audit, ensure_unit_access, get_current_user, require, scoped_unit_ids
from .common import apply_scope, get_period

router = APIRouter(prefix="/api", tags=["Danh mục & đơn vị"])

CATEGORY_NAMES = {
    "ubnd_tinh": "UBND tỉnh", "van_phong": "Văn phòng UBND tỉnh", "so_nganh": "Sở, ban, ngành",
    "ubnd_xa": "UBND xã, phường", "thpt": "Trường THPT", "thcs": "Trường THCS", "tieu_hoc": "Trường Tiểu học",
    "mam_non": "Trường Mầm non",
}


def unit_out(u: Unit, dti: DTIScore | None = None) -> dict:
    d = {"id": u.id, "code": u.code, "name": u.name, "unit_type": u.unit_type, "category": u.category,
         "category_name": CATEGORY_NAMES.get(u.category, u.category), "level": u.level,
         "region_id": u.region_id, "region_name": u.region.name if u.region else None,
         "parent_unit_id": u.parent_unit_id, "address": u.address, "head_name": u.head_name, "phone": u.phone,
         "email": u.email, "staff_count": u.staff_count, "student_count": u.student_count, "is_active": u.is_active}
    if dti is not None:
        d.update(dti_score=dti.score, dti_level=dti.level, rank=dti.rank_overall, delta_prev=dti.delta_prev)
    return d


# ------------------------------------------------------------ địa bàn


@router.get("/regions")
def regions(db: Session = Depends(get_db), _=Depends(get_current_user)):
    counts = dict(db.execute(select(Unit.region_id, func.count()).group_by(Unit.region_id)).all())
    return [{"id": r.id, "code": r.code, "name": r.name, "type": r.type, "parent_id": r.parent_id,
             "population": r.population, "area_km2": r.area_km2, "unit_count": counts.get(r.id, 0)}
            for r in db.scalars(select(Region).order_by(Region.type.desc(), Region.name))]


@router.get("/periods")
def periods(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [{"id": p.id, "code": p.code, "name": p.name, "year": p.year, "quarter": p.quarter,
             "start_date": p.start_date, "end_date": p.end_date, "is_current": p.is_current, "is_locked": p.is_locked,
             "published_at": p.published_at, "publish_decision": p.publish_decision}
            for p in db.scalars(select(Period).order_by(Period.start_date))]


# ------------------------------------------------------------ đơn vị


@router.get("/units")
def list_units(q: str | None = None, unit_type: str | None = None, category: str | None = None,
               region_id: int | None = None, level: str | None = None, period: str | None = None,
               page: int = 1, size: int = 20, sort: str = "name",
               db: Session = Depends(get_db), user: User = Depends(require("unit.view"))):
    p = get_period(db, period)
    stmt = select(Unit, DTIScore).outerjoin(DTIScore, (DTIScore.unit_id == Unit.id) & (DTIScore.period_id == p.id))
    stmt = apply_scope(stmt, Unit.id, scoped_unit_ids(db, user))
    if q:
        stmt = stmt.where(or_(Unit.name.ilike(f"%{q}%"), Unit.code.ilike(f"%{q}%")))
    for col, val in ((Unit.unit_type, unit_type), (Unit.category, category), (Unit.region_id, region_id), (Unit.level, level)):
        if val:
            stmt = stmt.where(col == val)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"name": Unit.name, "dti_desc": DTIScore.score.desc().nulls_last(), "dti_asc": DTIScore.score.asc().nulls_last(),
             "code": Unit.code}.get(sort, Unit.name)
    rows = db.execute(stmt.order_by(order).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "items": [unit_out(u, d) for u, d in rows]}


@router.get("/units/options")
def unit_options(unit_type: str | None = None, level: str | None = None, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    stmt = select(Unit.id, Unit.name, Unit.code, Unit.unit_type, Unit.level).where(Unit.is_active)
    if unit_type:
        stmt = stmt.where(Unit.unit_type == unit_type)
    if level:
        stmt = stmt.where(Unit.level == level)
    return [dict(id=i, name=n, code=c, unit_type=t, level=lv) for i, n, c, t, lv in db.execute(stmt.order_by(Unit.name))]


@router.get("/units/{uid}")
def unit_detail(uid: int, period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("unit.view"))):
    ensure_unit_access(db, user, uid)
    u = db.get(Unit, uid)
    if not u:
        raise HTTPException(404, "Không tìm thấy đơn vị")
    p = get_period(db, period)
    dti = db.get(DTIScore, (uid, p.id))
    history = db.execute(select(Period.code, DTIScore.score, DTIScore.level, DTIScore.rank_overall)
                         .join(Period, Period.id == DTIScore.period_id).where(DTIScore.unit_id == uid)
                         .order_by(Period.start_date)).all()
    pillars = db.execute(select(Pillar.code, Pillar.name, Pillar.weight, PillarScore.score)
                         .join(PillarScore, (PillarScore.pillar_id == Pillar.id) & (PillarScore.unit_id == uid)
                               & (PillarScore.period_id == p.id), isouter=True).order_by(Pillar.sort_order)).all()
    # trung bình cùng loại hình để so sánh
    peer = dict(db.execute(select(Pillar.code, func.avg(PillarScore.score)).join(PillarScore)
                           .join(Unit, Unit.id == PillarScore.unit_id)
                           .where(PillarScore.period_id == p.id, Unit.unit_type == u.unit_type)
                           .group_by(Pillar.code)).all())
    crits = db.execute(select(Criterion, CriterionScore.value, CriterionScore.score)
                       .outerjoin(CriterionScore, (CriterionScore.criterion_id == Criterion.id)
                                  & (CriterionScore.unit_id == uid) & (CriterionScore.period_id == p.id))
                       .where(Criterion.unit_type.in_(["all", u.unit_type]), Criterion.is_active)
                       .order_by(Criterion.code)).all()
    infra = db.get(UnitInfra, uid)
    services = db.scalars(select(UnitService).where(UnitService.unit_id == uid)).all()
    recs = db.scalars(select(Recommendation).where(Recommendation.unit_id == uid, Recommendation.period_id == p.id)
                      .order_by(Recommendation.priority_score.desc())).all()
    cluster = db.get(UnitCluster, (uid, p.id))
    return {
        "unit": unit_out(u, dti), "period": p.code,
        "dti": {"score": dti.score, "level": dti.level, "rank_overall": dti.rank_overall, "rank_in_group": dti.rank_in_group,
                "delta_prev": dti.delta_prev, "completeness": dti.completeness} if dti else None,
        "history": [{"period": c, "score": s, "level": lv, "rank": r} for c, s, lv, r in history],
        "pillars": [{"code": c, "name": n, "weight": w, "score": s, "peer_avg": round(float(peer.get(c) or 0), 1)}
                    for c, n, w, s in pillars],
        "criteria": [{"code": c.code, "name": c.name, "pillar": c.pillar.code, "metric_type": c.metric_type,
                      "target": c.target, "unit_label": c.unit_label, "source": c.source, "value": v, "score": s}
                     for c, v, s in crits],
        "infra": {k: getattr(infra, k) for k in ("computers", "servers", "internet_mbps", "has_lan", "has_wifi",
                                                  "has_firewall", "has_backup", "has_camera", "smart_classrooms")} if infra else None,
        "services": [{"id": s.id, "service_id": s.service_id, "code": s.service.code, "name": s.service.name,
                      "category": s.service.category, "status": s.status, "start_date": s.start_date,
                      "end_date": s.end_date, "usage_level": s.usage_level, "monthly_fee": float(s.monthly_fee or 0)}
                     for s in services],
        "recommendations": [{"id": r.id, "code": r.solution.code, "name": r.solution.name, "pillar": r.solution.pillar.name,
                             "priority_score": r.priority_score, "priority_level": r.priority_level, "reason": r.reason,
                             "actions": r.solution.actions, "missing_services": r.missing_services,
                             "duration_months": r.solution.duration_months, "cost_level": r.solution.cost_level}
                            for r in recs],
        "cluster": {"label": cluster.cluster_label, "forecast_next": cluster.forecast_next,
                    "trend_slope": cluster.trend_slope} if cluster else None,
    }


class UnitIn(BaseModel):
    code: str
    name: str
    unit_type: str
    category: str
    level: str
    region_id: int
    parent_unit_id: int | None = None
    address: str | None = None
    head_name: str | None = None
    phone: str | None = None
    email: str | None = None
    staff_count: int | None = None
    student_count: int | None = None
    is_active: bool = True


@router.post("/units")
def create_unit(body: UnitIn, request: Request, db: Session = Depends(get_db), me=Depends(require("unit.manage", "catalog.manage"))):
    if db.scalar(select(Unit).where(Unit.code == body.code)):
        raise HTTPException(400, "Mã đơn vị đã tồn tại")
    u = Unit(**body.model_dump())
    db.add(u)
    db.flush()
    db.add(UnitInfra(unit_id=u.id))
    audit(db, me, "create", "unit", u.id, {"code": u.code}, request)
    db.commit()
    db.refresh(u)
    return unit_out(u)


@router.put("/units/{uid}")
def update_unit(uid: int, body: UnitIn, request: Request, db: Session = Depends(get_db), me=Depends(require("unit.manage", "catalog.manage"))):
    u = db.get(Unit, uid)
    if not u:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(u, k, v)
    audit(db, me, "update", "unit", uid, None, request)
    db.commit()
    db.refresh(u)
    return unit_out(u)


class InfraIn(BaseModel):
    computers: int = 0
    servers: int = 0
    internet_mbps: int = 0
    has_lan: bool = False
    has_wifi: bool = False
    has_firewall: bool = False
    has_backup: bool = False
    has_camera: bool = False
    smart_classrooms: int = 0


@router.put("/units/{uid}/infra")
def update_infra(uid: int, body: InfraIn, request: Request, db: Session = Depends(get_db),
                 me=Depends(require("unit.manage", "unit.self_update"))):
    """Sở KH&CN cập nhật mọi đơn vị; đơn vị (quyền unit.self_update) chỉ tự khai báo hạ tầng của mình."""
    from ..security import perms_of
    if "unit.manage" not in perms_of(me) and me.unit_id != uid:
        raise HTTPException(403, "Chỉ được cập nhật hạ tầng của đơn vị mình")
    inf = db.get(UnitInfra, uid) or UnitInfra(unit_id=uid)
    for k, v in body.model_dump().items():
        setattr(inf, k, v)
    db.add(inf)
    audit(db, me, "update", "unit_infra", uid, body.model_dump(), request)
    db.commit()
    return {"ok": True}


class UnitServiceIn(BaseModel):
    service_id: int
    status: str
    start_date: date | None = None
    end_date: date | None = None
    usage_level: int = 0
    monthly_fee: float = 0


@router.post("/units/{uid}/services")
def upsert_unit_service(uid: int, body: UnitServiceIn, request: Request, db: Session = Depends(get_db),
                        me=Depends(require("unit.manage", "am.view"))):
    ensure_unit_access(db, me, uid)
    s = db.scalar(select(UnitService).where(UnitService.unit_id == uid, UnitService.service_id == body.service_id))
    s = s or UnitService(unit_id=uid, service_id=body.service_id)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.add(s)
    audit(db, me, "upsert", "unit_service", uid, body.model_dump(mode="json"), request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------ dịch vụ, tiêu chí, giải pháp


@router.get("/services")
def services(db: Session = Depends(get_db), _=Depends(get_current_user)):
    used = dict(db.execute(select(UnitService.service_id, func.count()).where(UnitService.status == "dang_dung")
                           .group_by(UnitService.service_id)).all())
    return [{"id": s.id, "code": s.code, "name": s.name, "provider": s.provider, "category": s.category,
             "pillar_code": s.pillar_code, "unit_types": s.unit_types, "monthly_price": float(s.monthly_price),
             "description": s.description, "active_units": used.get(s.id, 0)}
            for s in db.scalars(select(ServiceCatalog).order_by(ServiceCatalog.category, ServiceCatalog.name))]


@router.get("/framework")
def framework(db: Session = Depends(get_db), _=Depends(require("criteria.manage", "data.import", "score.compute"))):
    """Bộ tiêu chí đánh giá: trụ cột → tiêu chí (kèm trọng số, mục tiêu)."""
    pillars = db.scalars(select(Pillar).order_by(Pillar.sort_order)).all()
    crits = db.scalars(select(Criterion).order_by(Criterion.code)).all()
    return [{"id": p.id, "code": p.code, "name": p.name, "description": p.description, "weight": p.weight,
             "criteria": [{"id": c.id, "code": c.code, "name": c.name, "description": c.description,
                           "unit_type": c.unit_type, "metric_type": c.metric_type, "target": c.target,
                           "weight": c.weight, "unit_label": c.unit_label, "source": c.source, "is_active": c.is_active}
                          for c in crits if c.pillar_id == p.id]} for p in pillars]


class PillarWeightIn(BaseModel):
    weight: float


class CriterionIn(BaseModel):
    weight: float
    target: float
    is_active: bool = True


@router.put("/framework/pillars/{pid}")
def update_pillar(pid: int, body: PillarWeightIn, request: Request, db: Session = Depends(get_db), me=Depends(require("criteria.manage"))):
    p = db.get(Pillar, pid)
    p.weight = body.weight
    audit(db, me, "update", "pillar", pid, body.model_dump(), request)
    db.commit()
    return {"ok": True}


@router.put("/framework/criteria/{cid}")
def update_criterion(cid: int, body: CriterionIn, request: Request, db: Session = Depends(get_db), me=Depends(require("criteria.manage"))):
    c = db.get(Criterion, cid)
    if body.target <= 0:
        raise HTTPException(400, "Giá trị mục tiêu phải > 0")
    c.weight, c.target, c.is_active = body.weight, body.target, body.is_active
    audit(db, me, "update", "criterion", cid, body.model_dump(), request)
    db.commit()
    return {"ok": True}


@router.get("/solutions")
def solutions(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [{"id": s.id, "code": s.code, "name": s.name, "pillar": s.pillar.name, "pillar_code": s.pillar.code,
             "unit_type": s.unit_type, "trigger_criteria": s.trigger_criteria, "description": s.description,
             "actions": s.actions, "service_codes": s.service_codes, "cost_level": s.cost_level,
             "duration_months": s.duration_months}
            for s in db.scalars(select(SolutionGroup).order_by(SolutionGroup.code))]



class ServiceIn(BaseModel):
    code: str
    name: str
    provider: str = "VNPT"
    category: str
    pillar_code: str | None = None
    unit_types: list[str]
    monthly_price: float = 0
    description: str | None = None


@router.post("/services")
def create_service(body: ServiceIn, request: Request, db: Session = Depends(get_db), me=Depends(require("unit.manage"))):
    if db.scalar(select(ServiceCatalog).where(ServiceCatalog.code == body.code)):
        raise HTTPException(400, "Mã dịch vụ đã tồn tại")
    s = ServiceCatalog(**body.model_dump())
    db.add(s)
    audit(db, me, "create", "service", body.code, body.model_dump(), request)
    db.commit()
    return {"id": s.id}


@router.put("/services/{sid}")
def update_service(sid: int, body: ServiceIn, request: Request, db: Session = Depends(get_db), me=Depends(require("unit.manage"))):
    s = db.get(ServiceCatalog, sid)
    if not s:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude={"code"}).items():
        setattr(s, k, v)
    audit(db, me, "update", "service", s.code, body.model_dump(), request)
    db.commit()
    return {"ok": True}


@router.delete("/units/{uid}/services/{usid}")
def delete_unit_service(uid: int, usid: int, request: Request, db: Session = Depends(get_db),
                        me=Depends(require("unit.manage", "am.view"))):
    ensure_unit_access(db, me, uid)
    s = db.get(UnitService, usid)
    if not s or s.unit_id != uid:
        raise HTTPException(404)
    db.delete(s)
    audit(db, me, "delete", "unit_service", usid, request=request)
    db.commit()
    return {"ok": True}
