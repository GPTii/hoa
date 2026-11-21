"""Data pipeline theo kiến trúc Medallion: Nguồn → Bronze → Silver → Gold.

Bronze : lưu nguyên trạng từng dòng dữ liệu nguồn (JSONB) + thông tin lô nhập → truy vết được.
Silver : làm sạch & chuẩn hóa – ánh xạ mã đơn vị, chuẩn hóa kỳ, ép kiểu giá trị, kiểm tra miền giá trị,
         loại trùng; bản ghi lỗi đưa vào silver.rejected_records kèm lý do.
Gold   : xem services/scoring.py (tính điểm tiêu chí, trụ cột, DTI, cảnh báo, đề xuất).
"""
from __future__ import annotations

import io
import math
import re
from datetime import date

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..models import (
    Criterion, IngestBatch, Period, RawRecord, RejectedRecord, Task, TaskAssignment, Unit, UnitInfra,
    UnitMetric, UnitService,
)

UNIT_COL_ALIASES = {"ma_don_vi", "madonvi", "mã đơn vị", "ma dv", "unit_code", "ma_dv"}
PERIOD_COL_ALIASES = {"ky_danh_gia", "ky", "kỳ", "kỳ đánh giá", "period", "ky_bao_cao"}
CRIT_COL_ALIASES = {"ma_tieu_chi", "mã tiêu chí", "criterion", "tieu_chi"}
VALUE_COL_ALIASES = {"gia_tri", "giá trị", "value"}
TRUE_WORDS = {"1", "có", "co", "yes", "y", "true", "x", "đạt", "dat", "rồi", "đã có"}
FALSE_WORDS = {"0", "không", "khong", "no", "n", "false", "chưa", "chua", "chưa có"}


# ------------------------------------------------------------------ helpers chuẩn hóa

def normalize_period(raw) -> str | None:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    s = str(raw).strip().lower().replace("quý", "q").replace("quy", "q").replace(" ", "")
    m = re.match(r"^(\d{4})[-_/]?q([1-4])$", s) or None
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    m = re.match(r"^q([1-4])[-_/]?(\d{4})$", s)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    return None


def parse_value(raw, crit: Criterion) -> tuple[float | None, str | None]:
    """Trả về (giá trị chuẩn hóa, lỗi). (None, None) = ô trống, bỏ qua."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None, None
    s = str(raw).strip()
    if s == "" or s.lower() in {"nan", "none", "-", "n/a"}:
        return None, None
    if crit.metric_type == "boolean":
        low = s.lower()
        if low in TRUE_WORDS:
            return 1.0, None
        if low in FALSE_WORDS:
            return 0.0, None
        return None, f"Giá trị '{s}' không phải Có/Không"
    has_pct = "%" in s
    s2 = s.replace("%", "").replace(" ", "")
    # 1.234,5 → 1234.5 ; 12,5 → 12.5
    if s2.count(",") == 1 and s2.count(".") >= 1:
        s2 = s2.replace(".", "").replace(",", ".")
    else:
        s2 = s2.replace(",", ".")
    try:
        v = float(s2)
    except ValueError:
        return None, f"Không chuyển được '{s}' sang số"
    if crit.metric_type == "ratio":
        if not has_pct and 0 < v < 1:
            v = v * 100  # dữ liệu nhập dạng phân số 0.85 → 85%
        if v < 0 or v > 100:
            return None, f"Tỷ lệ {v} nằm ngoài miền [0, 100]"
    elif v < 0:
        return None, f"Giá trị âm {v} không hợp lệ"
    return round(v, 4), None


def _pick(cols: dict[str, str], aliases: set[str]) -> str | None:
    for low, orig in cols.items():
        if low in aliases:
            return orig
    return None


# ------------------------------------------------------------------ BRONZE

def ingest_file(db: Session, content: bytes, file_name: str, user_id: int | None,
                period_code: str | None = None) -> IngestBatch:
    """Đọc file CSV/XLSX và lưu NGUYÊN TRẠNG vào bronze.raw_records."""
    if file_name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), dtype=str)
        source = "upload_xlsx"
    else:
        text = None
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sep = ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
        df = pd.read_csv(io.StringIO(text), dtype=str, sep=sep)
        source = "upload_csv"
    df.columns = [str(c).strip() for c in df.columns]
    batch = IngestBatch(source_type=source, file_name=file_name, uploaded_by=user_id,
                        period_code=normalize_period(period_code) if period_code else None,
                        total_rows=len(df), status="bronze")
    db.add(batch)
    db.flush()
    records = [
        {"batch_id": batch.id, "row_no": i + 2,  # +2: dòng tiêu đề là dòng 1
         "payload": {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in row.items()}}
        for i, row in enumerate(df.to_dict(orient="records"))
    ]
    if records:
        db.execute(pg_insert(RawRecord), records)
    db.commit()
    return batch


# ------------------------------------------------------------------ SILVER

def bronze_to_silver(db: Session, batch: IngestBatch) -> IngestBatch:
    units = {u.code.strip().upper(): u for u in db.scalars(select(Unit))}
    crits = {c.code.upper(): c for c in db.scalars(select(Criterion).where(Criterion.is_active))}
    periods = {p.code: p for p in db.scalars(select(Period))}
    rows = db.scalars(select(RawRecord).where(RawRecord.batch_id == batch.id).order_by(RawRecord.row_no)).all()

    db.query(RejectedRecord).filter(RejectedRecord.batch_id == batch.id).delete()
    rejected: list[dict] = []
    cleaned: dict[tuple[int, int, int], dict] = {}  # khóa (unit, period, criterion) → loại trùng, dòng sau ghi đè

    def reject(row_no, col, raw, reason):
        rejected.append({"batch_id": batch.id, "row_no": row_no, "column_name": col,
                         "raw_value": None if raw is None else str(raw)[:250], "reason": reason})

    def accept(row_no, unit, period, crit_code, raw, col):
        crit = crits.get(str(crit_code).strip().upper())
        if not crit:
            return reject(row_no, col, crit_code, "Mã tiêu chí không tồn tại")
        if crit.unit_type not in ("all", unit.unit_type):
            return  # tiêu chí không áp dụng cho loại hình đơn vị → bỏ qua (không phải lỗi)
        value, err = parse_value(raw, crit)
        if err:
            return reject(row_no, col, raw, err)
        if value is None:
            return
        cleaned[(unit.id, period.id, crit.id)] = {
            "batch_id": batch.id, "unit_id": unit.id, "period_id": period.id, "criterion_id": crit.id,
            "raw_value": None if raw is None else str(raw)[:100], "value": value, "source": "survey",
        }

    if rows:
        cols = {k.strip().lower(): k for k in rows[0].payload.keys()}
        ucol, pcol = _pick(cols, UNIT_COL_ALIASES), _pick(cols, PERIOD_COL_ALIASES)
        ccol, vcol = _pick(cols, CRIT_COL_ALIASES), _pick(cols, VALUE_COL_ALIASES)
        long_format = bool(ccol and vcol)
        if not ucol:
            batch.status, batch.message = "failed", "Không tìm thấy cột mã đơn vị (ma_don_vi)"
            db.commit()
            return batch
        for r in rows:
            p = r.payload
            raw_unit = p.get(ucol)
            unit = units.get(str(raw_unit).strip().upper()) if raw_unit else None
            if not unit:
                reject(r.row_no, ucol, raw_unit, "Mã đơn vị không tồn tại trong danh mục")
                continue
            pcode = normalize_period(p.get(pcol)) if pcol else None
            pcode = pcode or batch.period_code
            period = periods.get(pcode) if pcode else None
            if not period:
                reject(r.row_no, pcol, p.get(pcol) if pcol else None, "Kỳ đánh giá không hợp lệ/không xác định")
                continue
            if period.is_locked:
                reject(r.row_no, pcol, period.code, "Kỳ đánh giá đã khóa số liệu – không nhận dữ liệu mới")
                continue
            if long_format:
                accept(r.row_no, unit, period, p.get(ccol), p.get(vcol), vcol)
            else:
                for col, raw in p.items():
                    if col in (ucol, pcol) or col.strip().lower() in {"ten_don_vi", "tên đơn vị", "ghi_chu", "ghi chú"}:
                        continue
                    accept(r.row_no, unit, period, col, raw, col)

    if cleaned:
        stmt = pg_insert(UnitMetric).values(list(cleaned.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["unit_id", "period_id", "criterion_id"],
            set_={"value": stmt.excluded.value, "raw_value": stmt.excluded.raw_value,
                  "batch_id": stmt.excluded.batch_id, "source": stmt.excluded.source, "updated_at": func.now()},
        )
        db.execute(stmt)
    if rejected:
        db.execute(pg_insert(RejectedRecord), rejected)
    batch.valid_values, batch.rejected_values = len(cleaned), len(rejected)
    batch.status = "silver"
    batch.message = f"Chuẩn hóa {len(cleaned)} giá trị hợp lệ, loại {len(rejected)} giá trị lỗi"
    db.commit()
    return batch


# ------------------------------------------------------------------ SILVER: đồng bộ từ dữ liệu vận hành

def sync_operational(db: Session, period: Period, user_id: int | None = None,
                     parts: tuple[str, ...] = ("tasks", "infra", "services")) -> IngestBatch:
    """Sinh chỉ số tự động từ dữ liệu vận hành trong hệ thống (không cần nhập tay):
    - HD03: tỷ lệ nhiệm vụ hoàn thành đúng hạn (từ module giao & theo dõi nhiệm vụ)
    - HT02, AT02, AT03: băng thông, tường lửa, sao lưu (từ hồ sơ hạ tầng)
    - DV06: mức độ khai thác các dịch vụ số đang dùng (từ danh mục dịch vụ của đơn vị)
    Mỗi lần đồng bộ cũng ghi một lô Bronze để truy vết nguồn gốc số liệu.
    """
    crits = {c.code: c for c in db.scalars(select(Criterion))}
    batch = IngestBatch(source_type="system_sync", file_name=f"Đồng bộ dữ liệu vận hành {period.code}",
                        period_code=period.code, uploaded_by=user_id, status="bronze")
    db.add(batch)
    db.flush()
    values: dict[tuple[int, int], tuple[float, str]] = {}
    today = date.today()
    ref_day = min(today, period.end_date)

    # nhiệm vụ có hạn trong kỳ
    q = (select(TaskAssignment, Task.deadline).join(Task, Task.id == TaskAssignment.task_id)
         .where(Task.deadline >= period.start_date, Task.deadline <= period.end_date,
                TaskAssignment.role == "chu_tri", TaskAssignment.status != "khong_tiep_nhan"))
    stats: dict[int, list[int]] = {}
    for a, deadline in db.execute(q):
        if deadline > ref_day and a.status != "hoan_thanh":
            continue  # chưa đến hạn → chưa đánh giá
        on_time = a.status == "hoan_thanh" and a.confirmed_at and a.confirmed_at.date() <= deadline
        s = stats.setdefault(a.unit_id, [0, 0])
        s[0] += 1
        s[1] += 1 if on_time else 0
    if "HD03" in crits and "tasks" in parts:
        for uid, (total, ok) in stats.items():
            values[(uid, crits["HD03"].id)] = (round(ok * 100 / total, 2), "tasks")

    for inf in (db.scalars(select(UnitInfra)) if "infra" in parts else []):
        if "HT02" in crits:
            values[(inf.unit_id, crits["HT02"].id)] = (float(inf.internet_mbps), "infra")
        if "AT02" in crits:
            values[(inf.unit_id, crits["AT02"].id)] = (1.0 if inf.has_firewall else 0.0, "infra")
        if "AT03" in crits:
            values[(inf.unit_id, crits["AT03"].id)] = (1.0 if inf.has_backup else 0.0, "infra")

    if "DV06" in crits and "services" in parts:
        usage = db.execute(select(UnitService.unit_id, func.avg(UnitService.usage_level))
                           .where(UnitService.status.in_(["dang_dung", "dung_thu"]))
                           .group_by(UnitService.unit_id)).all()
        for uid, avg in usage:
            values[(uid, crits["DV06"].id)] = (round(float(avg), 2), "services")

    unit_types = dict(db.execute(select(Unit.id, Unit.unit_type)).all())
    crit_by_id = {c.id: c for c in crits.values()}
    raw, rows = [], []
    for i, ((uid, cid), (v, src)) in enumerate(values.items()):
        c = crit_by_id[cid]
        if c.unit_type not in ("all", unit_types.get(uid)):
            continue
        raw.append({"batch_id": batch.id, "row_no": i + 1,
                    "payload": {"unit_id": uid, "criterion": c.code, "value": v, "source": src}})
        rows.append({"batch_id": batch.id, "unit_id": uid, "period_id": period.id, "criterion_id": cid,
                     "raw_value": str(v), "value": v, "source": src})
    if raw:
        db.execute(pg_insert(RawRecord), raw)
    if rows:
        for i in range(0, len(rows), 2000):
            stmt = pg_insert(UnitMetric).values(rows[i:i + 2000])
            stmt = stmt.on_conflict_do_update(
                index_elements=["unit_id", "period_id", "criterion_id"],
                set_={"value": stmt.excluded.value, "raw_value": stmt.excluded.raw_value,
                      "batch_id": stmt.excluded.batch_id, "source": stmt.excluded.source, "updated_at": func.now()},
            )
            db.execute(stmt)
    batch.total_rows = batch.valid_values = len(rows)
    batch.status = "silver"
    batch.message = f"Đồng bộ {len(rows)} chỉ số từ nhiệm vụ, hạ tầng, dịch vụ số"
    db.commit()
    return batch
