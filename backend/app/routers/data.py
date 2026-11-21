import io

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Criterion, IngestBatch, RawRecord, RejectedRecord, Unit, UnitMetric, User
from ..security import audit, require
from ..services import ml, pipeline, scoring
from .common import get_period

router = APIRouter(prefix="/api/data", tags=["Tích hợp & xử lý dữ liệu"])


def batch_out(b: IngestBatch, uploader: str | None = None) -> dict:
    return {"id": b.id, "source_type": b.source_type, "file_name": b.file_name, "period_code": b.period_code,
            "uploaded_at": b.uploaded_at, "uploaded_by": uploader, "status": b.status, "total_rows": b.total_rows,
            "valid_values": b.valid_values, "rejected_values": b.rejected_values, "message": b.message}


@router.get("/batches")
def batches(page: int = 1, size: int = 15, db: Session = Depends(get_db), _=Depends(require("data.view", "data.import"))):
    total = db.scalar(select(func.count(IngestBatch.id)))
    rows = db.execute(select(IngestBatch, User.full_name).outerjoin(User, User.id == IngestBatch.uploaded_by)
                      .order_by(IngestBatch.id.desc()).offset((page - 1) * size).limit(size)).all()
    layer = {
        "bronze": db.scalar(select(func.count(RawRecord.id))),
        "silver": db.scalar(select(func.count(UnitMetric.id))),
        "rejected": db.scalar(select(func.count(RejectedRecord.id))),
    }
    from ..models import CriterionScore, DTIScore
    layer["gold"] = db.scalar(select(func.count()).select_from(CriterionScore)) + db.scalar(select(func.count()).select_from(DTIScore))
    return {"total": total, "layers": layer, "items": [batch_out(b, n) for b, n in rows]}


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...), period: str | None = Form(None),
                 auto_process: bool = Form(True), db: Session = Depends(get_db), user: User = Depends(require("data.import"))):
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "Chỉ hỗ trợ tệp CSV hoặc Excel")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Tệp vượt quá 10MB")
    try:
        batch = pipeline.ingest_file(db, content, file.filename, user.id, period)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Không đọc được tệp: {e}")
    audit(db, user, "upload", "batch", batch.id, {"file": file.filename}, request)
    db.commit()
    result = {"batch": batch_out(batch)}
    if auto_process:
        result = process(batch.id, request, db, user)
    return result


@router.post("/batches/{bid}/process")
def process(bid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require("data.import"))):
    """Chạy toàn bộ pipeline cho một lô: Bronze → Silver → Gold (tính lại các kỳ bị ảnh hưởng)."""
    batch = db.get(IngestBatch, bid)
    if not batch:
        raise HTTPException(404)
    batch = pipeline.bronze_to_silver(db, batch)
    if batch.status == "failed":
        return {"batch": batch_out(batch), "gold": []}
    period_ids = list(db.scalars(select(UnitMetric.period_id).where(UnitMetric.batch_id == bid).distinct()))
    from ..models import Period
    gold = []
    for p in db.scalars(select(Period).where(Period.id.in_(period_ids or [-1])).order_by(Period.start_date)):
        gold.append(scoring.compute_period(db, p))
        ml.run_clustering(db, p)
    batch.status = "gold"
    audit(db, user, "process", "batch", bid, {"periods": [g["period"] for g in gold]}, request)
    db.commit()
    return {"batch": batch_out(batch), "gold": gold}


@router.get("/batches/{bid}/rejected")
def rejected(bid: int, db: Session = Depends(get_db), _=Depends(require("data.view", "data.import"))):
    return [{"row_no": r.row_no, "column_name": r.column_name, "raw_value": r.raw_value, "reason": r.reason}
            for r in db.scalars(select(RejectedRecord).where(RejectedRecord.batch_id == bid).order_by(RejectedRecord.row_no).limit(500))]


@router.get("/batches/{bid}/raw")
def raw(bid: int, db: Session = Depends(get_db), _=Depends(require("data.view", "data.import"))):
    return [{"row_no": r.row_no, "payload": r.payload}
            for r in db.scalars(select(RawRecord).where(RawRecord.batch_id == bid).order_by(RawRecord.row_no).limit(100))]


@router.post("/sync")
def sync(request: Request, period: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("score.compute"))):
    """Đồng bộ chỉ số từ dữ liệu vận hành (nhiệm vụ, hạ tầng, dịch vụ) rồi tính lại Gold cho kỳ."""
    p = get_period(db, period)
    if p.is_locked:
        raise HTTPException(409, f"Kỳ {p.code} đã khóa số liệu")
    b = pipeline.sync_operational(db, p, user.id)
    g = scoring.compute_period(db, p)
    ml.run_clustering(db, p)
    b.status = "gold"
    audit(db, user, "sync", "period", p.code, g, request)
    db.commit()
    return {"batch": batch_out(b), "gold": g}


@router.post("/recompute")
def recompute(request: Request, period: str | None = None, all_periods: bool = False, db: Session = Depends(get_db),
              user: User = Depends(require("score.compute"))):
    if all_periods:
        res = scoring.compute_all(db)
        from ..models import Period
        for p in db.scalars(select(Period)):
            ml.run_clustering(db, p)
    else:
        p = get_period(db, period)
        if p.is_locked:
            raise HTTPException(409, f"Kỳ {p.code} đã khóa số liệu – không tính lại")
        res = [scoring.compute_period(db, p)]
        ml.run_clustering(db, p)
    audit(db, user, "recompute", "score", None, {"result": res}, request)
    db.commit()
    return res


@router.post("/ml/cluster")
def cluster(period: str | None = None, k: int = 4, db: Session = Depends(get_db), _=Depends(require("ml.run"))):
    return ml.run_clustering(db, get_period(db, period), k)


@router.get("/template")
def template(period: str | None = None, unit_type: str = "hanh_chinh", db: Session = Depends(get_db),
             _=Depends(require("data.import", "data.view"))):
    """Tải mẫu nhập liệu (dạng bảng rộng) cho loại hình đơn vị."""
    p = get_period(db, period)
    crits = db.scalars(select(Criterion).where(Criterion.is_active, Criterion.source == "survey",
                                               Criterion.unit_type.in_(["all", unit_type])).order_by(Criterion.code)).all()
    units = db.scalars(select(Unit).where(Unit.unit_type == unit_type, Unit.is_active).order_by(Unit.code)).all()
    df = pd.DataFrame([{"ma_don_vi": u.code, "ten_don_vi": u.name, "ky_danh_gia": p.code, **{c.code: "" for c in crits}}
                       for u in units])
    guide = pd.DataFrame([{"ma_tieu_chi": c.code, "ten_tieu_chi": c.name, "kieu": c.metric_type,
                           "muc_tieu": c.target, "don_vi": c.unit_label} for c in crits])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="du_lieu")
        guide.to_excel(w, index=False, sheet_name="huong_dan")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=mau_nhap_{unit_type}_{p.code}.xlsx"})



@router.get("/ml/evaluate")
def ml_evaluate(period: str | None = None, db: Session = Depends(get_db), _=Depends(require("ml.run"))):
    return ml.evaluate(db, get_period(db, period))
