"""Tầng GOLD: tính Digital Transformation Score (DTI) và các sản phẩm phân tích.

Quy trình (theo đề cương mục 4.5 – 4.7):
  Dữ liệu đơn vị (silver.unit_metrics)
    → Chuẩn hóa điểm tiêu chí  : score = min(value / target, 1) × 100  (boolean: 0 | 100)
    → Điểm trụ cột             : trung bình có trọng số các tiêu chí áp dụng (thiếu dữ liệu = 0 điểm)
    → DTI Score                : Σ (điểm trụ cột × trọng số trụ cột) / Σ trọng số   (thang 0–100)
    → Phân loại mức độ         : Khởi đầu / Cơ bản / Phát triển / Nâng cao / Dẫn đầu
    → Xếp hạng, so sánh kỳ trước, tổng hợp theo địa bàn
    → Cảnh báo, chỉ số ưu tiên, đề xuất nhóm giải pháp
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..models import (
    Alert, Criterion, CriterionScore, DTIScore, Period, Pillar, PillarScore, PriorityUnit, Recommendation,
    RegionScore, SolutionGroup, Task, TaskAssignment, Unit, UnitMetric, UnitService,
)

LEVELS = [(85, "Dẫn đầu"), (70, "Nâng cao"), (50, "Phát triển"), (30, "Cơ bản"), (0, "Khởi đầu")]


def classify(score: float) -> str:
    for th, name in LEVELS:
        if score >= th:
            return name
    return "Khởi đầu"


def _bulk(db: Session, model, rows: list[dict], chunk: int = 3000):
    for i in range(0, len(rows), chunk):
        db.execute(pg_insert(model), rows[i:i + chunk])


def compute_period(db: Session, period: Period) -> dict:
    pillars = {p.id: p for p in db.scalars(select(Pillar))}
    crits = [c for c in db.scalars(select(Criterion).where(Criterion.is_active))]
    units = pd.DataFrame(db.execute(select(Unit.id, Unit.unit_type, Unit.region_id, Unit.category)
                                    .where(Unit.is_active)).all(),
                         columns=["unit_id", "unit_type", "region_id", "category"])
    metrics = pd.DataFrame(db.execute(select(UnitMetric.unit_id, UnitMetric.criterion_id, UnitMetric.value)
                                      .where(UnitMetric.period_id == period.id)).all(),
                           columns=["unit_id", "criterion_id", "value"])
    for model in (CriterionScore, PillarScore, DTIScore, RegionScore, Alert, Recommendation, PriorityUnit):
        db.execute(delete(model).where(model.period_id == period.id))
    if metrics.empty:
        db.commit()
        return {"period": period.code, "units": 0}

    # ---- 1. điểm tiêu chí: lưới đầy đủ đơn vị × tiêu chí áp dụng (thiếu dữ liệu → 0 điểm)
    crit_df = pd.DataFrame([{"criterion_id": c.id, "pillar_id": c.pillar_id, "c_unit_type": c.unit_type,
                             "metric_type": c.metric_type, "target": c.target, "c_weight": c.weight,
                             "c_source": c.source} for c in crits])
    measured_units = units[units.unit_id.isin(metrics.unit_id.unique())]
    grid = measured_units.merge(crit_df, how="cross")
    grid = grid[(grid.c_unit_type == "all") | (grid.c_unit_type == grid.unit_type)]
    grid = grid.merge(metrics, on=["unit_id", "criterion_id"], how="left")
    # Tiêu chí tính từ nhiệm vụ: đơn vị không có nhiệm vụ đến hạn trong kỳ → không áp dụng (không trừ điểm)
    grid = grid[~((grid.c_source == "tasks") & grid.value.isna())]
    grid["has_value"] = grid.value.notna()
    grid["score"] = 0.0
    m = grid.has_value
    grid.loc[m, "score"] = (grid.loc[m, "value"] / grid.loc[m, "target"]).clip(0, 1) * 100
    grid.loc[m & (grid.metric_type == "boolean"), "score"] = grid.loc[m & (grid.metric_type == "boolean"), "value"].clip(0, 1) * 100
    grid["score"] = grid.score.round(2)
    _bulk(db, CriterionScore, [
        {"unit_id": int(r.unit_id), "period_id": period.id, "criterion_id": int(r.criterion_id),
         "value": float(r.value), "score": float(r.score)}
        for r in grid[m].itertuples()])

    # ---- 2. điểm trụ cột
    grid["ws"] = grid.score * grid.c_weight
    ps = grid.groupby(["unit_id", "pillar_id"]).agg(ws=("ws", "sum"), w=("c_weight", "sum")).reset_index()
    ps["score"] = (ps.ws / ps.w).round(2)
    _bulk(db, PillarScore, [{"unit_id": int(r.unit_id), "period_id": period.id, "pillar_id": int(r.pillar_id),
                             "score": float(r.score)} for r in ps.itertuples()])

    # ---- 3. DTI
    ps["pw"] = ps.pillar_id.map(lambda x: pillars[x].weight)
    ps["wscore"] = ps.score * ps.pw
    dti = ps.groupby("unit_id").agg(ws=("wscore", "sum"), w=("pw", "sum")).reset_index()
    dti["score"] = (dti.ws / dti.w).round(2)
    comp = grid.groupby("unit_id").has_value.mean().mul(100).round(1).rename("completeness")
    dti = dti.merge(comp, on="unit_id").merge(units, on="unit_id")
    dti["level"] = dti.score.map(classify)
    dti["rank_overall"] = dti.score.rank(ascending=False, method="min").astype(int)
    dti["rank_in_group"] = dti.groupby("unit_type").score.rank(ascending=False, method="min").astype(int)
    prev = db.scalar(select(Period).where(Period.start_date < period.start_date).order_by(Period.start_date.desc()))
    prev_scores = {}
    if prev:
        prev_scores = dict(db.execute(select(DTIScore.unit_id, DTIScore.score).where(DTIScore.period_id == prev.id)).all())
    dti["delta_prev"] = dti.apply(lambda r: round(r.score - prev_scores[r.unit_id], 2) if r.unit_id in prev_scores else None, axis=1)
    _bulk(db, DTIScore, [{"unit_id": int(r.unit_id), "period_id": period.id, "score": float(r.score), "level": r.level,
                          "rank_overall": int(r.rank_overall), "rank_in_group": int(r.rank_in_group),
                          "delta_prev": None if pd.isna(r.delta_prev) else float(r.delta_prev),
                          "completeness": float(r.completeness)} for r in dti.itertuples()])

    # ---- 4. tổng hợp theo địa bàn (xã/phường)
    rg = dti.groupby("region_id").agg(avg_score=("score", "mean"), unit_count=("score", "size"),
                                      min_score=("score", "min"), max_score=("score", "max")).reset_index()
    by_type = dti.pivot_table(index="region_id", columns="unit_type", values="score", aggfunc="mean")
    rg["admin_avg"] = rg.region_id.map(by_type.get("hanh_chinh", pd.Series(dtype=float)))
    rg["edu_avg"] = rg.region_id.map(by_type.get("giao_duc", pd.Series(dtype=float)))
    rg["rank"] = rg.avg_score.rank(ascending=False, method="min").astype(int)
    _bulk(db, RegionScore, [{"region_id": int(r.region_id), "period_id": period.id, "avg_score": round(float(r.avg_score), 2),
                             "admin_avg": None if pd.isna(r.admin_avg) else round(float(r.admin_avg), 2),
                             "edu_avg": None if pd.isna(r.edu_avg) else round(float(r.edu_avg), 2),
                             "unit_count": int(r.unit_count), "min_score": float(r.min_score),
                             "max_score": float(r.max_score), "rank": int(r.rank)} for r in rg.itertuples()])

    # ---- 5. cảnh báo + chỉ số ưu tiên
    ref_day = min(date.today(), period.end_date)
    task_rows = db.execute(select(TaskAssignment.unit_id, TaskAssignment.status, TaskAssignment.confirmed_at, Task.deadline)
                           .join(Task, Task.id == TaskAssignment.task_id).where(Task.deadline >= period.start_date, Task.deadline <= period.end_date,
                                             TaskAssignment.status != "khong_tiep_nhan")).all()
    overdue: dict[int, list[int]] = {}
    for uid, st, conf, dl in task_rows:
        s = overdue.setdefault(uid, [0, 0])
        s[0] += 1
        late_open = st != "hoan_thanh" and dl < ref_day
        late_done = st == "hoan_thanh" and conf and conf.date() > dl
        s[1] += 1 if (late_open or late_done) else 0
    weak = ps[ps.score < 30].groupby("unit_id").pillar_id.apply(list).to_dict()

    alerts_rows = _alerts_with_unit(dti, ps, pillars, weak, overdue, period)
    prio = []
    for r in dti.itertuples():
        uid = int(r.unit_id)
        tot, late = overdue.get(uid, [0, 0])
        drop = 0 if pd.isna(r.delta_prev) else max(-r.delta_prev, 0)
        reasons = []
        if r.score < 40:
            reasons.append(f"DTI thấp {r.score:.1f}")
        if drop >= 5:
            reasons.append(f"giảm {drop:.1f} điểm")
        if weak.get(uid):
            reasons.append(f"{len(weak[uid])} trụ cột yếu")
        if late:
            reasons.append(f"{late} nhiệm vụ trễ hạn")
        if r.completeness < 80:
            reasons.append("thiếu dữ liệu")
        # Chỉ số ưu tiên (0–100): càng cao càng cần quan tâm sớm
        idx = (0.55 * (100 - r.score) + 0.15 * min(drop * 5, 100)
               + 0.15 * (late / tot * 100 if tot else 0) + 0.15 * (len(weak.get(uid, [])) / len(pillars) * 100))
        prio.append({"unit_id": uid, "period_id": period.id, "priority_index": round(idx, 2),
                     "reasons": ", ".join(reasons) or "Duy trì, theo dõi định kỳ"})
    prio.sort(key=lambda x: -x["priority_index"])
    for rank, p in enumerate(prio, 1):
        p["rank"] = rank
    _bulk(db, Alert, alerts_rows)
    _bulk(db, PriorityUnit, prio)

    # ---- 6. cảnh báo dịch vụ sắp hết hạn (chỉ kỳ hiện hành)
    if period.is_current:
        exp = db.execute(select(UnitService).where(UnitService.status.in_(["dang_dung", "dung_thu"]),
                                                   UnitService.end_date <= date.today() + timedelta(days=60))).scalars().all()
        _bulk(db, Alert, [{"unit_id": s.unit_id, "period_id": period.id, "alert_type": "EXPIRING_SERVICE", "severity": "thap",
                           "message": f"Dịch vụ {s.service.name} hết hạn ngày {s.end_date:%d/%m/%Y}", "metric_value": None}
                          for s in exp])

    # ---- 7. đề xuất nhóm giải pháp
    recs = recommend(db, period, grid, units)
    _bulk(db, Recommendation, recs)
    db.commit()
    return {"period": period.code, "units": int(len(dti)), "avg_dti": round(float(dti.score.mean()), 2),
            "alerts": len(alerts_rows), "recommendations": len(recs)}


def _alerts_with_unit(dti, ps, pillars, weak, overdue, period):
    rows = []
    for r in dti.itertuples():
        uid = int(r.unit_id)

        def add(t, sev, msg, val):
            rows.append({"unit_id": uid, "period_id": period.id, "alert_type": t, "severity": sev,
                         "message": msg, "metric_value": None if val is None else float(val)})
        if r.score < 40:
            add("LOW_SCORE", "cao" if r.score < 30 else "trung_binh", f"Chỉ số DTI thấp ({r.score:.1f} điểm – mức {r.level})", r.score)
        if not pd.isna(r.delta_prev) and r.delta_prev <= -5:
            add("SCORE_DROP", "cao" if r.delta_prev <= -10 else "trung_binh", f"DTI giảm {abs(r.delta_prev):.1f} điểm so với kỳ trước", r.delta_prev)
        for pid in weak.get(uid, []):
            sc = float(ps[(ps.unit_id == uid) & (ps.pillar_id == pid)].score.iloc[0])
            add("WEAK_PILLAR", "trung_binh", f"Trụ cột '{pillars[pid].name}' yếu ({sc:.1f} điểm)", sc)
        tot, late = overdue.get(uid, [0, 0])
        if late:
            add("OVERDUE_TASK", "cao" if late >= 2 else "trung_binh", f"{late}/{tot} nhiệm vụ được giao trễ hạn", late)
        if r.completeness < 80:
            add("MISSING_DATA", "thap", f"Dữ liệu đánh giá mới đầy đủ {r.completeness:.0f}%", r.completeness)
    return rows


def recommend(db: Session, period: Period, grid: pd.DataFrame, units: pd.DataFrame) -> list[dict]:
    """Luật đề xuất: nhóm giải pháp được kích hoạt khi điểm trung bình các tiêu chí kích hoạt ≤ 60.
    Mức ưu tiên = độ thiếu hụt (100 − điểm) điều chỉnh theo trọng số trụ cột."""
    groups = list(db.scalars(select(SolutionGroup)))
    crits = {c.code: c.id for c in db.scalars(select(Criterion))}
    crit_names = {c.id: c.name for c in db.scalars(select(Criterion))}
    active = {}
    for uid, code in db.execute(select(UnitService.unit_id, UnitService.service_id)
                                .where(UnitService.status.in_(["dang_dung", "dung_thu"]))):
        active.setdefault(uid, set()).add(code)
    from ..models import ServiceCatalog
    svc_code = dict(db.execute(select(ServiceCatalog.id, ServiceCatalog.code)).all())
    active_codes = {u: {svc_code[s] for s in ss} for u, ss in active.items()}
    score_map = {(r.unit_id, r.criterion_id): r.score for r in grid[["unit_id", "criterion_id", "score"]].itertuples()}
    utype = dict(zip(units.unit_id, units.unit_type))
    out = []
    for uid in grid.unit_id.unique():
        uid = int(uid)
        for g in groups:
            if g.unit_type not in ("all", utype.get(uid)):
                continue
            cids = [crits[c] for c in g.trigger_criteria if c in crits and (uid, crits[c]) in score_map]
            if not cids:
                continue
            scores = [score_map[(uid, c)] for c in cids]
            avg = sum(scores) / len(scores)
            if avg > 60:
                continue
            gap = 100 - avg
            prio = round(min(gap * (0.6 + 0.4 * g.pillar.weight / 20), 100), 2)
            level = "cao" if prio >= 70 else "trung_binh" if prio >= 50 else "thap"
            weakest = sorted(zip(cids, scores), key=lambda x: x[1])[:2]
            reason = "; ".join(f"{crit_names[c]}: {s:.0f}/100 điểm" for c, s in weakest)
            missing = [s for s in g.service_codes if s not in active_codes.get(uid, set())]
            out.append({"unit_id": uid, "period_id": period.id, "solution_group_id": g.id, "priority_score": prio,
                        "priority_level": level, "reason": reason, "missing_services": missing})
    return out


def compute_all(db: Session) -> list[dict]:
    """Tính lại mọi kỳ chưa khóa số liệu (kỳ đã khóa giữ nguyên kết quả đã công bố)."""
    return [compute_period(db, p) for p in db.scalars(select(Period).where(~Period.is_locked).order_by(Period.start_date))]
