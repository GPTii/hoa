from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Alert, DTIScore, Period, Pillar, PillarScore, PriorityUnit, Recommendation, Region, SolutionGroup, Task,
    TaskAssignment, Unit, UnitCluster, User,
)
from ..security import require, scoped_unit_ids
from ..services.scoring import LEVELS
from .common import apply_scope, get_period

router = APIRouter(prefix="/api/analytics", tags=["Phân tích & đánh giá"])


def _unit_filter(stmt, db, user, unit_type=None, region_id=None):
    stmt = apply_scope(stmt, Unit.id, scoped_unit_ids(db, user))
    if unit_type:
        stmt = stmt.where(Unit.unit_type == unit_type)
    if region_id:
        stmt = stmt.where(Unit.region_id == region_id)
    return stmt


@router.get("/overview")
def overview(period: str | None = None, unit_type: str | None = None, region_id: int | None = None,
             db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    p = get_period(db, period)
    base = select(DTIScore, Unit).join(Unit, Unit.id == DTIScore.unit_id).where(DTIScore.period_id == p.id)
    base = _unit_filter(base, db, user, unit_type, region_id)
    rows = db.execute(base).all()
    scores = [d.score for d, _ in rows]
    prev = db.scalar(select(Period).where(Period.start_date < p.start_date).order_by(Period.start_date.desc()))
    prev_avg = None
    if prev:
        q = _unit_filter(select(func.avg(DTIScore.score)).join(Unit, Unit.id == DTIScore.unit_id)
                         .where(DTIScore.period_id == prev.id), db, user, unit_type, region_id)
        prev_avg = db.scalar(q)
    avg = sum(scores) / len(scores) if scores else 0
    levels = {name: 0 for _, name in LEVELS}
    for d, _ in rows:
        levels[d.level] += 1

    # xu hướng theo kỳ
    tq = _unit_filter(select(Period.code, Unit.unit_type, func.avg(DTIScore.score), func.count())
                      .join(DTIScore, DTIScore.period_id == Period.id).join(Unit, Unit.id == DTIScore.unit_id),
                      db, user, unit_type, region_id).group_by(Period.code, Period.start_date, Unit.unit_type).order_by(Period.start_date)
    trend: dict[str, dict] = {}
    for code, ut, a, n in db.execute(tq):
        t = trend.setdefault(code, {"period": code})
        t[ut] = round(float(a), 2)
    tq_all = _unit_filter(select(Period.code, func.avg(DTIScore.score)).join(DTIScore, DTIScore.period_id == Period.id)
                          .join(Unit, Unit.id == DTIScore.unit_id), db, user, unit_type, region_id) \
        .group_by(Period.code, Period.start_date).order_by(Period.start_date)
    for code, a in db.execute(tq_all):
        trend[code]["all"] = round(float(a), 2)

    # trụ cột
    pq = _unit_filter(select(Pillar.code, Pillar.name, func.avg(PillarScore.score)).join(PillarScore)
                      .join(Unit, Unit.id == PillarScore.unit_id).where(PillarScore.period_id == p.id),
                      db, user, unit_type, region_id).group_by(Pillar.code, Pillar.name, Pillar.sort_order).order_by(Pillar.sort_order)
    pillars = [{"code": c, "name": n, "avg": round(float(a), 1)} for c, n, a in db.execute(pq)]

    # theo loại hình đơn vị
    cq = _unit_filter(select(Unit.category, func.avg(DTIScore.score), func.count()).join(DTIScore, DTIScore.unit_id == Unit.id)
                      .where(DTIScore.period_id == p.id), db, user, unit_type, region_id).group_by(Unit.category)
    from .catalog import CATEGORY_NAMES
    by_category = [{"category": c, "name": CATEGORY_NAMES.get(c, c), "avg": round(float(a), 1), "count": n}
                   for c, a, n in db.execute(cq)]

    ranked = sorted(rows, key=lambda r: -r[0].score)

    def brief(d, u):
        return {"id": u.id, "name": u.name, "unit_type": u.unit_type, "region": u.region.name, "score": d.score,
                "level": d.level, "delta_prev": d.delta_prev}

    aq = _unit_filter(select(Alert.severity, func.count()).join(Unit, Unit.id == Alert.unit_id)
                      .where(Alert.period_id == p.id), db, user, unit_type, region_id).group_by(Alert.severity)
    alerts = dict(db.execute(aq).all())

    # nhiệm vụ
    tk = _unit_filter(select(TaskAssignment.status, Task.deadline).join(Task, Task.id == TaskAssignment.task_id).join(Unit, Unit.id == TaskAssignment.unit_id),
                      db, user, unit_type, region_id)
    from datetime import date
    today = date.today()
    tstats = {"total": 0, "hoan_thanh": 0, "dang_xu_ly": 0, "qua_han": 0, "chua_tiep_nhan": 0}
    for st, dl in db.execute(tk):
        tstats["total"] += 1
        if st == "hoan_thanh":
            tstats["hoan_thanh"] += 1
        elif st == "chua_tiep_nhan":
            tstats["chua_tiep_nhan"] += 1
        else:
            tstats["dang_xu_ly"] += 1
        if st not in ("hoan_thanh", "khong_tiep_nhan") and dl < today:
            tstats["qua_han"] += 1

    # điểm theo địa bàn (chỉ hiển thị khi phạm vi rộng hơn một xã)
    rq = _unit_filter(select(Region.id, Region.name, func.avg(DTIScore.score), func.count())
                      .join(Unit, Unit.region_id == Region.id).join(DTIScore, DTIScore.unit_id == Unit.id)
                      .where(DTIScore.period_id == p.id, Region.type != "tinh"), db, user, unit_type, region_id) \
        .group_by(Region.id, Region.name).order_by(func.avg(DTIScore.score).desc())
    regions = [{"id": i, "name": n, "avg": round(float(a), 1), "count": c} for i, n, a, c in db.execute(rq)]

    return {
        "period": p.code, "published": bool(p.published_at), "publish_decision": p.publish_decision, "prev_period": prev.code if prev else None,
        "kpi": {"units": len(rows), "avg_dti": round(avg, 2),
                "delta_avg": round(avg - float(prev_avg), 2) if prev_avg else None,
                "max": max(scores) if scores else None, "min": min(scores) if scores else None,
                "alerts_high": alerts.get("cao", 0), "alerts_total": sum(alerts.values()),
                "priority_units": sum(1 for d, _ in rows if d.score < 40)},
        "levels": [{"level": k, "count": v} for k, v in levels.items()][::-1],
        "trend": list(trend.values()), "pillars": pillars, "by_category": by_category,
        "top": [brief(d, u) for d, u in ranked[:5]], "bottom": [brief(d, u) for d, u in ranked[-5:][::-1]],
        "tasks": tstats, "regions": regions,
        "histogram": [{"bin": f"{b}-{b + 10}", "count": sum(1 for s in scores if b <= s < b + 10 or (b == 90 and s == 100))}
                      for b in range(0, 100, 10)],
    }


@router.get("/ranking")
def ranking(period: str | None = None, unit_type: str | None = None, region_id: int | None = None,
            level: str | None = None, q: str | None = None, page: int = 1, size: int = 20,
            db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    p = get_period(db, period)
    stmt = _unit_filter(select(DTIScore, Unit, UnitCluster.cluster_label)
                        .join(Unit, Unit.id == DTIScore.unit_id)
                        .outerjoin(UnitCluster, (UnitCluster.unit_id == Unit.id) & (UnitCluster.period_id == p.id))
                        .where(DTIScore.period_id == p.id), db, user, unit_type, region_id)
    if level:
        stmt = stmt.where(DTIScore.level == level)
    if q:
        stmt = stmt.where(Unit.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(DTIScore.score.desc()).offset((page - 1) * size).limit(size)).all()
    ids = [u.id for _, u, _ in rows]
    pil = {}
    for uid, code, sc in db.execute(select(PillarScore.unit_id, Pillar.code, PillarScore.score).join(Pillar)
                                    .where(PillarScore.period_id == p.id, PillarScore.unit_id.in_(ids or [-1]))):
        pil.setdefault(uid, {})[code] = sc
    return {"total": total, "items": [{
        "unit_id": u.id, "name": u.name, "unit_type": u.unit_type, "category": u.category, "region": u.region.name,
        "score": d.score, "level": d.level, "rank": d.rank_overall, "rank_in_group": d.rank_in_group,
        "delta_prev": d.delta_prev, "completeness": d.completeness, "cluster": cl, "pillars": pil.get(u.id, {}),
    } for d, u, cl in rows]}


@router.get("/regions")
def region_analysis(period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    p = get_period(db, period)
    stmt = _unit_filter(select(Region.id, Region.name, Region.type, Region.population,
                               func.avg(DTIScore.score), func.min(DTIScore.score), func.max(DTIScore.score), func.count(),
                               func.avg(case((Unit.unit_type == "hanh_chinh", DTIScore.score))),
                               func.avg(case((Unit.unit_type == "giao_duc", DTIScore.score))),
                               func.sum(case((DTIScore.score < 40, 1), else_=0)))
                        .join(Unit, Unit.region_id == Region.id).join(DTIScore, DTIScore.unit_id == Unit.id)
                        .where(DTIScore.period_id == p.id), db, user).group_by(Region.id).order_by(func.avg(DTIScore.score).desc())
    rows = db.execute(stmt).all()
    pil = {}
    pq = _unit_filter(select(Unit.region_id, Pillar.code, func.avg(PillarScore.score)).select_from(PillarScore)
                      .join(Pillar, Pillar.id == PillarScore.pillar_id).join(Unit, Unit.id == PillarScore.unit_id)
                      .where(PillarScore.period_id == p.id), db, user) \
        .group_by(Unit.region_id, Pillar.code)
    for rid, code, a in db.execute(pq):
        pil.setdefault(rid, {})[code] = round(float(a), 1)
    return [{"region_id": r[0], "name": r[1], "type": r[2], "population": r[3], "avg": round(float(r[4]), 2),
             "min": r[5], "max": r[6], "count": r[7], "admin_avg": round(float(r[8]), 1) if r[8] else None,
             "edu_avg": round(float(r[9]), 1) if r[9] else None, "low_count": int(r[10]), "rank": i + 1,
             "pillars": pil.get(r[0], {})} for i, r in enumerate(rows)]


@router.get("/compare")
def compare(unit_ids: str, period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    p = get_period(db, period)
    ids = [int(x) for x in unit_ids.split(",") if x.strip().isdigit()][:6]
    scope = scoped_unit_ids(db, user)
    if scope is not None:
        ids = [i for i in ids if i in scope]
    out = []
    for uid in ids:
        u = db.get(Unit, uid)
        pil = dict(db.execute(select(Pillar.code, PillarScore.score).join(PillarScore)
                              .where(PillarScore.unit_id == uid, PillarScore.period_id == p.id)).all())
        hist = db.execute(select(Period.code, DTIScore.score).join(DTIScore, DTIScore.period_id == Period.id)
                          .where(DTIScore.unit_id == uid).order_by(Period.start_date)).all()
        d = db.get(DTIScore, (uid, p.id))
        out.append({"unit_id": uid, "name": u.name, "score": d.score if d else None, "level": d.level if d else None,
                    "pillars": pil, "history": [{"period": c, "score": s} for c, s in hist]})
    return out


@router.get("/alerts")
def alerts(period: str | None = None, alert_type: str | None = None, severity: str | None = None,
           unit_type: str | None = None, region_id: int | None = None, page: int = 1, size: int = 20,
           db: Session = Depends(get_db), user: User = Depends(require("alert.view"))):
    p = get_period(db, period)
    stmt = _unit_filter(select(Alert, Unit).join(Unit, Unit.id == Alert.unit_id).where(Alert.period_id == p.id),
                        db, user, unit_type, region_id)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    sev_order = case((Alert.severity == "cao", 0), (Alert.severity == "trung_binh", 1), else_=2)
    rows = db.execute(stmt.order_by(sev_order, Alert.id).offset((page - 1) * size).limit(size)).all()
    counts = dict(db.execute(_unit_filter(select(Alert.alert_type, func.count()).join(Unit, Unit.id == Alert.unit_id)
                                          .where(Alert.period_id == p.id), db, user, unit_type, region_id)
                             .group_by(Alert.alert_type)).all())
    return {"total": total, "counts": counts, "items": [
        {"id": a.id, "unit_id": u.id, "unit_name": u.name, "region": u.region.name, "unit_type": u.unit_type,
         "alert_type": a.alert_type, "severity": a.severity, "message": a.message, "metric_value": a.metric_value}
        for a, u in rows]}


@router.get("/priority")
def priority(period: str | None = None, unit_type: str | None = None, region_id: int | None = None, limit: int = 20,
             db: Session = Depends(get_db), user: User = Depends(require("alert.view"))):
    p = get_period(db, period)
    stmt = _unit_filter(select(PriorityUnit, Unit, DTIScore).join(Unit, Unit.id == PriorityUnit.unit_id)
                        .join(DTIScore, (DTIScore.unit_id == Unit.id) & (DTIScore.period_id == p.id))
                        .where(PriorityUnit.period_id == p.id), db, user, unit_type, region_id)
    rows = db.execute(stmt.order_by(PriorityUnit.priority_index.desc()).limit(limit)).all()
    return [{"unit_id": u.id, "name": u.name, "region": u.region.name, "unit_type": u.unit_type,
             "priority_index": pu.priority_index, "score": d.score, "level": d.level, "delta_prev": d.delta_prev,
             "reasons": pu.reasons} for pu, u, d in rows]


@router.get("/planning")
def planning(period: str | None = None, unit_type: str | None = None, region_id: int | None = None,
             db: Session = Depends(get_db), user: User = Depends(require("plan.view"))):
    """Hỗ trợ hoạch định: tổng hợp đề xuất theo nhóm giải pháp + trụ cột yếu theo phạm vi."""
    p = get_period(db, period)
    stmt = _unit_filter(select(Recommendation.solution_group_id, func.count(Recommendation.id),
                               func.avg(Recommendation.priority_score),
                               func.sum(case((Recommendation.priority_level == "cao", 1), else_=0)))
                        .join(Unit, Unit.id == Recommendation.unit_id).where(Recommendation.period_id == p.id),
                        db, user, unit_type, region_id).group_by(Recommendation.solution_group_id) \
        .order_by(func.count(Recommendation.id).desc())
    groups = []
    for gid, n, a, h in db.execute(stmt).all():
        g = db.get(SolutionGroup, gid)
        groups.append({"id": g.id, "code": g.code, "name": g.name, "pillar": g.pillar.name, "pillar_code": g.pillar.code,
                       "actions": g.actions, "service_codes": g.service_codes, "cost_level": g.cost_level,
                       "duration_months": g.duration_months, "unit_count": n, "avg_priority": round(float(a), 1),
                       "high_count": int(h)})
    wq = _unit_filter(select(Pillar.code, Pillar.name,
                             func.sum(case((PillarScore.score < 30, 1), else_=0)),
                             func.sum(case(((PillarScore.score >= 30) & (PillarScore.score < 50), 1), else_=0)),
                             func.sum(case((PillarScore.score >= 50, 1), else_=0)))
                      .join(PillarScore).join(Unit, Unit.id == PillarScore.unit_id).where(PillarScore.period_id == p.id),
                      db, user, unit_type, region_id).group_by(Pillar.code, Pillar.name, Pillar.sort_order).order_by(Pillar.sort_order)
    pillars = [{"code": c, "name": n, "weak": int(w), "medium": int(m), "good": int(g)} for c, n, w, m, g in db.execute(wq)]
    return {"period": p.code, "groups": groups, "pillars": pillars}


@router.get("/planning/{group_id}/units")
def planning_units(group_id: int, period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("plan.view"))):
    p = get_period(db, period)
    stmt = _unit_filter(select(Recommendation, Unit).join(Unit, Unit.id == Recommendation.unit_id)
                        .where(Recommendation.period_id == p.id, Recommendation.solution_group_id == group_id), db, user)
    return [{"unit_id": u.id, "name": u.name, "region": u.region.name, "priority_score": r.priority_score,
             "priority_level": r.priority_level, "reason": r.reason, "missing_services": r.missing_services}
            for r, u in db.execute(stmt.order_by(Recommendation.priority_score.desc()))]


@router.get("/clusters")
def clusters(period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("ml.run"))):
    p = get_period(db, period)
    stmt = _unit_filter(select(UnitCluster, Unit, DTIScore).join(Unit, Unit.id == UnitCluster.unit_id)
                        .join(DTIScore, (DTIScore.unit_id == Unit.id) & (DTIScore.period_id == p.id))
                        .where(UnitCluster.period_id == p.id), db, user)
    rows = db.execute(stmt).all()
    pil = {}
    for uid, code, sc in db.execute(select(PillarScore.unit_id, Pillar.code, PillarScore.score).join(Pillar)
                                    .where(PillarScore.period_id == p.id)):
        pil.setdefault(uid, {})[code] = sc
    groups: dict[int, dict] = {}
    for c, u, d in rows:
        g = groups.setdefault(c.cluster, {"cluster": c.cluster, "label": c.cluster_label, "size": 0, "sum": 0.0, "pillars": {}})
        g["size"] += 1
        g["sum"] += d.score
        for k, v in pil.get(u.id, {}).items():
            g["pillars"][k] = g["pillars"].get(k, 0) + v
    profile = [{"cluster": g["cluster"], "label": g["label"], "size": g["size"], "avg": round(g["sum"] / g["size"], 1),
                "pillars": {k: round(v / g["size"], 1) for k, v in g["pillars"].items()}}
               for g in sorted(groups.values(), key=lambda x: x["cluster"])]
    return {"period": p.code, "profile": profile,
            "units": [{"unit_id": u.id, "name": u.name, "unit_type": u.unit_type, "region": u.region.name,
                       "cluster": c.cluster, "label": c.cluster_label, "score": d.score, "forecast_next": c.forecast_next,
                       "trend_slope": c.trend_slope} for c, u, d in rows]}
