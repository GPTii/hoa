"""Quy trình đánh giá mức độ chuyển đổi số theo kỳ (tham chiếu Bộ chỉ số DTI và Quyết định 4725/QĐ-BGDĐT):

 1. ĐƠN VỊ TỰ ĐÁNH GIÁ: chuyên viên / giáo viên phụ trách khai giá trị từng tiêu chí kèm minh chứng (assess.prepare)
 2. LÃNH ĐẠO ĐƠN VỊ DUYỆT, NỘP phiếu (assess.submit)
 3. CƠ QUAN THẨM ĐỊNH xem xét từng tiêu chí: chấp nhận / điều chỉnh / yêu cầu giải trình (trả lại) (assess.review)
      – Sở KH&CN thẩm định cơ quan hành chính; Sở GD&ĐT thẩm định cơ sở giáo dục (theo phạm vi dữ liệu)
      – Phê duyệt → số liệu đi qua pipeline Bronze → Silver → Gold, tính DTI
 4. UBND TỈNH CÔNG BỐ kết quả chính thức của kỳ bằng quyết định (assess.publish) → khóa số liệu kỳ
Tiêu chí lấy tự động từ hệ thống (nhiệm vụ, hạ tầng, dịch vụ) không phải khai.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Assessment, AssessmentItem, Criterion, IngestBatch, Notification, Period, RawRecord, Role, Unit, UnitMetric, User,
)
from ..security import audit, perms_of, require, scoped_unit_ids
from ..services import ml, pipeline, scoring
from .common import get_period
from .tasks import notify, unit_users

router = APIRouter(prefix="/api/assessments", tags=["Tự đánh giá & thẩm định DTI"])
STATUS = {"nhap": "Đang lập", "da_nop": "Đã nộp – chờ thẩm định", "tra_lai": "Trả lại – giải trình/bổ sung",
          "da_tham_dinh": "Đã thẩm định"}


def _criteria_for(db: Session, unit: Unit) -> list[Criterion]:
    return list(db.scalars(select(Criterion).where(Criterion.is_active, Criterion.source == "survey",
                                                   Criterion.unit_type.in_(["all", unit.unit_type])).order_by(Criterion.code)))


def _estimate(items) -> float | None:
    """Ước tính điểm tự chấm: trung bình điểm chuẩn hóa các tiêu chí đã khai (chỉ để tham khảo)."""
    scores = []
    for it in items:
        raw = it.reviewer_value or it.value_raw
        v, err = pipeline.parse_value(raw, it.criterion)
        if v is not None and not err:
            scores.append(min(v / it.criterion.target, 1) * 100 if it.criterion.metric_type != "boolean" else v * 100)
    return round(sum(scores) / len(scores), 1) if scores else None


def a_out(a: Assessment, full: bool = False) -> dict:
    filled = sum(1 for i in a.items if (i.value_raw or "").strip())
    d = {"id": a.id, "unit_id": a.unit_id, "unit_name": a.unit.name, "unit_type": a.unit.unit_type, "region": a.unit.region.name,
         "period_id": a.period_id, "status": a.status, "status_name": STATUS[a.status], "prepared_by": a.prepared_by,
         "submitted_by": a.submitted_by, "submitted_at": a.submitted_at, "reviewed_by": a.reviewed_by, "reviewed_at": a.reviewed_at,
         "review_note": a.review_note, "self_score": a.self_score, "final_score": a.final_score,
         "filled": filled, "total": len(a.items), "adjusted": sum(1 for i in a.items if i.reviewer_value)}
    if full:
        d["items"] = [{"id": i.id, "criterion_id": i.criterion_id, "code": i.criterion.code, "name": i.criterion.name,
                       "pillar": i.criterion.pillar.name, "metric_type": i.criterion.metric_type, "target": i.criterion.target,
                       "unit_label": i.criterion.unit_label, "value_raw": i.value_raw, "evidence": i.evidence,
                       "reviewer_value": i.reviewer_value, "reviewer_note": i.reviewer_note} for i in a.items]
    return d


def _get_or_create(db: Session, unit: Unit, period: Period, user: User | None) -> Assessment:
    a = db.scalar(select(Assessment).where(Assessment.unit_id == unit.id, Assessment.period_id == period.id))
    if a:
        return a
    a = Assessment(unit_id=unit.id, period_id=period.id, status="nhap", prepared_by=user.full_name if user else None)
    db.add(a)
    db.flush()
    # gợi ý sẵn giá trị kỳ trước (đơn vị chỉ cần cập nhật thay đổi)
    prev = db.scalar(select(Period).where(Period.start_date < period.start_date).order_by(Period.start_date.desc()))
    prev_vals = dict(db.execute(select(UnitMetric.criterion_id, UnitMetric.raw_value).where(
        UnitMetric.unit_id == unit.id, UnitMetric.period_id == prev.id)).all()) if prev else {}
    for c in _criteria_for(db, unit):
        db.add(AssessmentItem(assessment_id=a.id, criterion_id=c.id, value_raw=prev_vals.get(c.id)))
    db.flush()
    db.refresh(a)
    return a


def _ensure_view(db: Session, user: User, a: Assessment):
    ids = scoped_unit_ids(db, user)
    if ids is not None and a.unit_id not in ids and user.unit_id != a.unit_id:
        raise HTTPException(403, "Phiếu nằm ngoài phạm vi của bạn")


@router.get("/mine")
def my_assessment(period: str | None = None, db: Session = Depends(get_db),
                  user: User = Depends(require("assess.prepare", "assess.submit"))):
    """Phiếu tự đánh giá của đơn vị mình trong kỳ (tự tạo nếu chưa có)."""
    if not user.unit_id:
        raise HTTPException(400, "Tài khoản không thuộc đơn vị nào")
    p = get_period(db, period)
    a = _get_or_create(db, user.unit, p, user)
    db.commit()
    d = a_out(a, full=True)
    d["period"] = {"code": p.code, "name": p.name, "is_locked": p.is_locked, "published_at": p.published_at}
    d["can_edit"] = a.status in ("nhap", "tra_lai") and not p.is_locked and bool(perms_of(user) & {"assess.prepare", "assess.submit"})
    d["can_submit"] = d["can_edit"] and "assess.submit" in perms_of(user)
    return d


class ItemIn(BaseModel):
    criterion_id: int
    value_raw: str | None = None
    evidence: str | None = None


@router.put("/{aid}/items")
def save_items(aid: int, items: list[ItemIn], request: Request, db: Session = Depends(get_db),
               user: User = Depends(require("assess.prepare", "assess.submit"))):
    a = db.get(Assessment, aid)
    if not a or a.unit_id != user.unit_id:
        raise HTTPException(403, "Chỉ đơn vị mình mới khai phiếu tự đánh giá")
    if a.status not in ("nhap", "tra_lai"):
        raise HTTPException(400, "Phiếu đã nộp, không sửa được")
    by_c = {i.criterion_id: i for i in a.items}
    errors = []
    for x in items:
        it = by_c.get(x.criterion_id)
        if not it:
            continue
        if x.value_raw not in (None, ""):
            v, err = pipeline.parse_value(x.value_raw, it.criterion)
            if err:
                errors.append(f"{it.criterion.code}: {err}")
                continue
        it.value_raw, it.evidence = x.value_raw, x.evidence
    a.prepared_by = user.full_name
    a.self_score = _estimate(a.items)
    audit(db, user, "save_assessment", "assessment", aid, {"items": len(items), "errors": len(errors)}, request)
    db.commit()
    return {"ok": not errors, "errors": errors, **a_out(a)}


class SubmitIn(BaseModel):
    note: str | None = None


@router.post("/{aid}/submit")
def submit(aid: int, body: SubmitIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("assess.submit"))):
    a = db.get(Assessment, aid)
    if not a or a.unit_id != user.unit_id:
        raise HTTPException(403, "Chỉ lãnh đạo đơn vị mới nộp phiếu của đơn vị mình")
    if a.status not in ("nhap", "tra_lai"):
        raise HTTPException(400, "Phiếu đã nộp")
    missing = [i.criterion.code for i in a.items if not (i.value_raw or "").strip()]
    if missing:
        raise HTTPException(400, f"Còn {len(missing)} tiêu chí chưa khai: {', '.join(missing[:6])}")
    no_ev = [i.criterion.code for i in a.items if not (i.evidence or "").strip()]
    if len(no_ev) > len(a.items) // 2:
        raise HTTPException(400, f"Thiếu minh chứng cho {len(no_ev)} tiêu chí – cần minh chứng cho ít nhất một nửa số tiêu chí")
    a.status, a.submitted_by, a.submitted_at = "da_nop", user.full_name, datetime.now()
    a.self_score = _estimate(a.items)
    # báo cho cơ quan thẩm định: Sở GD&ĐT với trường học, Sở KH&CN với cơ quan hành chính
    reviewers = db.scalars(select(User).join(Role, Role.id == User.role_id).where(User.is_active)).unique().all()
    for r in reviewers:
        if "assess.review" in perms_of(r):
            ids = scoped_unit_ids(db, r)
            if ids is None and r.role.data_scope == "all" and a.unit.unit_type == "giao_duc" and _has_edu_reviewer(db):
                continue  # trường học do Sở GD&ĐT thẩm định
            if ids is None or a.unit_id in ids:
                db.add(Notification(user_id=r.id, kind="bao_cao", title=f"Phiếu tự đánh giá chờ thẩm định: {a.unit.name}",
                                    body=body.note))
    audit(db, user, "submit_assessment", "assessment", aid, None, request)
    db.commit()
    return a_out(a)


def _has_edu_reviewer(db: Session) -> bool:
    return any("assess.review" in perms_of(u) and u.role.data_scope == "giao_duc"
               for u in db.scalars(select(User).join(Role, Role.id == User.role_id).where(User.is_active, Role.data_scope == "giao_duc")).unique())


def _review_scope(db: Session, user: User):
    """Phạm vi thẩm định: Sở GD&ĐT → trường học; Sở KH&CN (toàn tỉnh) → cơ quan hành chính (+ trường nếu không có Sở GD&ĐT)."""
    ids = scoped_unit_ids(db, user)
    stmt = select(Assessment).join(Unit, Unit.id == Assessment.unit_id)
    if ids is not None:
        stmt = stmt.where(Assessment.unit_id.in_(ids or [-1]))
    elif user.role.data_scope == "all" and _has_edu_reviewer(db):
        stmt = stmt.where(Unit.unit_type == "hanh_chinh")
    return stmt


@router.get("")
def list_assessments(period: str | None = None, status: str | None = None, db: Session = Depends(get_db),
                     user: User = Depends(require("assess.review", "assess.publish"))):
    p = get_period(db, period)
    base = (_review_scope(db, user) if "assess.review" in perms_of(user) else select(Assessment)).where(Assessment.period_id == p.id)
    all_rows = db.scalars(base.order_by(Assessment.submitted_at.desc().nulls_last(), Assessment.id)).unique().all()
    counts = {k: 0 for k in STATUS}
    for a in all_rows:
        counts[a.status] += 1
    rows = [a for a in all_rows if not status or a.status == status]
    total_units = len(all_rows)
    return {"period": {"code": p.code, "name": p.name, "published_at": p.published_at, "published_by": p.published_by,
                       "publish_decision": p.publish_decision, "is_locked": p.is_locked},
            "counts": counts, "total_units": total_units, "items": [a_out(a) for a in rows]}


@router.get("/{aid}")
def get_assessment(aid: int, db: Session = Depends(get_db), user: User = Depends(require("assess.prepare", "assess.submit", "assess.review", "assess.publish"))):
    a = db.get(Assessment, aid)
    if not a:
        raise HTTPException(404)
    _ensure_view(db, user, a)
    d = a_out(a, full=True)
    d["can_review"] = "assess.review" in perms_of(user) and a.status == "da_nop"
    return d


class ReviewItem(BaseModel):
    criterion_id: int
    reviewer_value: str | None = None
    reviewer_note: str | None = None


class ReviewIn(BaseModel):
    action: str  # approve | return
    note: str | None = None
    items: list[ReviewItem] = []


@router.post("/{aid}/review")
def review(aid: int, body: ReviewIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("assess.review"))):
    a = db.get(Assessment, aid)
    if not a:
        raise HTTPException(404)
    if not db.scalars(_review_scope(db, user).where(Assessment.id == aid)).first():
        raise HTTPException(403, "Phiếu không thuộc phạm vi thẩm định của bạn")
    if a.status != "da_nop":
        raise HTTPException(400, "Chỉ thẩm định phiếu đã nộp")
    p = db.get(Period, a.period_id)
    if p.is_locked:
        raise HTTPException(409, "Kỳ đã khóa số liệu")
    by_c = {i.criterion_id: i for i in a.items}
    for x in body.items:
        it = by_c.get(x.criterion_id)
        if not it:
            continue
        if x.reviewer_value not in (None, ""):
            v, err = pipeline.parse_value(x.reviewer_value, it.criterion)
            if err:
                raise HTTPException(400, f"{it.criterion.code}: {err}")
        it.reviewer_value, it.reviewer_note = x.reviewer_value or None, x.reviewer_note
    a.reviewed_by, a.reviewed_at, a.review_note = user.full_name, datetime.now(), body.note
    if body.action == "return":
        if not body.note:
            raise HTTPException(400, "Nhập nội dung yêu cầu giải trình/bổ sung")
        a.status = "tra_lai"
        notify(db, unit_users(db, a.unit_id, ("assess.prepare", "assess.submit")), "ket_qua",
               f"Phiếu tự đánh giá bị trả lại: {body.note}", None)
        audit(db, user, "return_assessment", "assessment", aid, {"note": body.note}, request)
        db.commit()
        return a_out(a)
    if body.action != "approve":
        raise HTTPException(400, "Hành động không hợp lệ")
    # phê duyệt → đưa số liệu cuối cùng qua pipeline (lưu vết Bronze) và tính lại Gold của kỳ
    batch = IngestBatch(source_type="tu_danh_gia", file_name=f"Phiếu tự đánh giá đã thẩm định – {a.unit.name}",
                        period_code=p.code, uploaded_by=user.id, total_rows=len(a.items), status="bronze")
    db.add(batch)
    db.flush()
    for n, it in enumerate(a.items, start=1):
        db.add(RawRecord(batch_id=batch.id, row_no=n, payload={"ma_don_vi": a.unit.code, "ky": p.code, "ma_tieu_chi": it.criterion.code,
                                                              "gia_tri": it.reviewer_value or it.value_raw, "minh_chung": it.evidence,
                                                              "gia_tri_tu_khai": it.value_raw}))
    db.flush()
    pipeline.bronze_to_silver(db, batch)
    scoring.compute_period(db, p)
    from ..models import DTIScore
    d = db.scalar(select(DTIScore).where(DTIScore.unit_id == a.unit_id, DTIScore.period_id == p.id))
    a.status, a.batch_id, a.final_score = "da_tham_dinh", batch.id, d.score if d else None
    batch.status = "gold"
    notify(db, unit_users(db, a.unit_id, ("assess.prepare", "assess.submit")), "ket_qua",
           f"Phiếu tự đánh giá đã được thẩm định – DTI {a.final_score} (tạm tính, chờ công bố)", None)
    audit(db, user, "approve_assessment", "assessment", aid, {"adjusted": sum(1 for i in a.items if i.reviewer_value)}, request)
    db.commit()
    return a_out(a)


class PublishIn(BaseModel):
    decision: str
    lock: bool = True


@router.post("/publish/{period_code}")
def publish(period_code: str, body: PublishIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("assess.publish"))):
    """UBND tỉnh công bố kết quả chính thức của kỳ (theo quyết định), mặc định khóa số liệu kỳ."""
    p = db.scalar(select(Period).where(Period.code == period_code))
    if not p:
        raise HTTPException(404)
    if p.published_at:
        raise HTTPException(400, "Kỳ đã được công bố")
    pending = db.scalar(select(func.count(Assessment.id)).where(Assessment.period_id == p.id, Assessment.status == "da_nop"))
    if pending:
        raise HTTPException(400, f"Còn {pending} phiếu chưa thẩm định – thẩm định xong mới công bố")
    if not body.decision.strip():
        raise HTTPException(400, "Nhập số quyết định công bố")
    ml.run_clustering(db, p)
    p.published_at, p.published_by, p.publish_decision = datetime.now(), user.full_name, body.decision.strip()
    if body.lock and not p.is_current:
        p.is_locked = True
    for uid in db.scalars(select(User.id).where(User.is_active)):
        db.add(Notification(user_id=uid, kind="he_thong", title=f"Công bố kết quả chuyển đổi số {p.name}",
                            body=f"Quyết định {p.publish_decision} – kết quả chính thức đã có trên hệ thống"))
    audit(db, user, "publish_period", "period", p.code, body.model_dump(), request)
    db.commit()
    return {"ok": True, "locked": p.is_locked}
