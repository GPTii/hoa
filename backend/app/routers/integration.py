"""API tích hợp cho hệ thống ngoài (LGSP tỉnh, VBĐH...) – xác thực bằng header X-API-Key (không dùng tài khoản người)."""
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ApiKey, DTIScore, IngestBatch, Period, RawRecord, Unit
from ..services import ml, pipeline, scoring
from .admin_ops import hash_key
from .common import get_period

router = APIRouter(prefix="/api/integration", tags=["Tích hợp hệ thống (API key)"])


def api_key(scope: str):
    def dep(x_api_key: str | None = Header(None), db: Session = Depends(get_db)) -> ApiKey:
        if not x_api_key:
            raise HTTPException(401, "Thiếu header X-API-Key")
        k = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(x_api_key)))
        if not k or k.revoked:
            raise HTTPException(401, "Khóa API không hợp lệ hoặc đã bị thu hồi")
        if k.expires_at and k.expires_at < datetime.now():
            raise HTTPException(401, "Khóa API đã hết hạn")
        if scope not in k.scopes:
            raise HTTPException(403, f"Khóa API không có quyền '{scope}'")
        k.last_used_at, k.use_count = datetime.now(), (k.use_count or 0) + 1
        db.commit()
        return k
    return dep


@router.get("/units")
def units(db: Session = Depends(get_db), _=Depends(api_key("units.read"))):
    return [{"code": u.code, "name": u.name, "unit_type": u.unit_type, "category": u.category, "region": u.region.name}
            for u in db.scalars(select(Unit).where(Unit.is_active).order_by(Unit.code))]


@router.get("/dti")
def dti(period: str | None = None, db: Session = Depends(get_db), _=Depends(api_key("dti.read"))):
    p = get_period(db, period)
    rows = db.execute(select(Unit, DTIScore).join(DTIScore, DTIScore.unit_id == Unit.id).where(DTIScore.period_id == p.id)
                      .order_by(DTIScore.rank_overall)).all()
    return {"period": p.code, "items": [{"code": u.code, "name": u.name, "score": d.score, "level": d.level, "rank": d.rank_overall}
                                        for u, d in rows]}


class MetricIn(BaseModel):
    unit_code: str
    criterion: str
    value: str


class PushIn(BaseModel):
    period: str
    source: str = "lgsp"
    metrics: list[MetricIn]


@router.post("/metrics")
def push_metrics(body: PushIn, db: Session = Depends(get_db), key: ApiKey = Depends(api_key("metrics.push"))):
    """Hệ thống ngoài đẩy số liệu dạng dài → đi qua đúng pipeline Bronze → Silver → Gold."""
    p = db.scalar(select(Period).where(Period.code == pipeline.normalize_period(body.period)))
    if not p:
        raise HTTPException(400, "Kỳ không hợp lệ")
    if p.is_locked:
        raise HTTPException(409, f"Kỳ {p.code} đã khóa số liệu")
    batch = IngestBatch(source_type="api", file_name=f"API: {key.name} ({body.source})", period_code=p.code,
                        total_rows=len(body.metrics), status="bronze")
    db.add(batch)
    db.flush()
    for i, m in enumerate(body.metrics, start=1):
        db.add(RawRecord(batch_id=batch.id, row_no=i, payload={"ma_don_vi": m.unit_code, "ky": p.code,
                                                               "ma_tieu_chi": m.criterion, "gia_tri": m.value}))
    db.commit()
    batch = pipeline.bronze_to_silver(db, batch)
    gold = scoring.compute_period(db, p)
    ml.run_clustering(db, p)
    batch.status = "gold"
    db.commit()
    return {"batch_id": batch.id, "valid": batch.valid_values, "rejected": batch.rejected_values, "gold": gold}
