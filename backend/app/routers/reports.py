import io
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, DTIScore, Pillar, PillarScore, Recommendation, Region, Unit, User
from ..security import audit, require, scoped_unit_ids
from .catalog import CATEGORY_NAMES
from .common import apply_scope, get_period

router = APIRouter(prefix="/api/reports", tags=["Báo cáo"])


@router.get("/dti.xlsx")
def export_dti(request: Request, period: str | None = None, unit_type: str | None = None, region_id: int | None = None,
               db: Session = Depends(get_db), user: User = Depends(require("report.export"))):
    """Báo cáo tổng hợp kết quả đánh giá chuyển đổi số (nhiều sheet) theo phạm vi phân quyền."""
    p = get_period(db, period)
    scope = scoped_unit_ids(db, user)
    stmt = apply_scope(select(Unit, DTIScore).join(DTIScore, DTIScore.unit_id == Unit.id).where(DTIScore.period_id == p.id),
                       Unit.id, scope)
    if unit_type:
        stmt = stmt.where(Unit.unit_type == unit_type)
    if region_id:
        stmt = stmt.where(Unit.region_id == region_id)
    rows = db.execute(stmt.order_by(DTIScore.rank_overall)).all()
    ids = [u.id for u, _ in rows]
    pillars = db.scalars(select(Pillar).order_by(Pillar.sort_order)).all()
    pil = {}
    for uid, pid, sc in db.execute(select(PillarScore.unit_id, PillarScore.pillar_id, PillarScore.score)
                                   .where(PillarScore.period_id == p.id, PillarScore.unit_id.in_(ids or [-1]))):
        pil[(uid, pid)] = sc
    df = pd.DataFrame([{
        "Hạng": d.rank_overall, "Mã đơn vị": u.code, "Tên đơn vị": u.name, "Loại hình": CATEGORY_NAMES.get(u.category),
        "Địa bàn": u.region.name, "DTI": d.score, "Mức độ": d.level, "Tăng/giảm so kỳ trước": d.delta_prev,
        "Độ đầy đủ dữ liệu (%)": d.completeness, **{pl.name: pil.get((u.id, pl.id)) for pl in pillars},
    } for u, d in rows])

    reg = df.groupby("Địa bàn").agg(**{"Số đơn vị": ("DTI", "size"), "DTI trung bình": ("DTI", "mean"),
                                       "Thấp nhất": ("DTI", "min"), "Cao nhất": ("DTI", "max")}).round(2) \
        .sort_values("DTI trung bình", ascending=False).reset_index() if not df.empty else pd.DataFrame()
    alerts = db.execute(select(Alert, Unit).join(Unit, Unit.id == Alert.unit_id)
                        .where(Alert.period_id == p.id, Alert.unit_id.in_(ids or [-1]))).all()
    adf = pd.DataFrame([{"Đơn vị": u.name, "Địa bàn": u.region.name, "Loại cảnh báo": a.alert_type,
                         "Mức độ": a.severity, "Nội dung": a.message} for a, u in alerts])
    recs = db.execute(select(Recommendation, Unit).join(Unit, Unit.id == Recommendation.unit_id)
                      .where(Recommendation.period_id == p.id, Recommendation.unit_id.in_(ids or [-1]))
                      .order_by(Recommendation.priority_score.desc())).all()
    rdf = pd.DataFrame([{"Đơn vị": u.name, "Nhóm giải pháp": r.solution.name, "Trụ cột": r.solution.pillar.name,
                         "Điểm ưu tiên": r.priority_score, "Mức ưu tiên": r.priority_level, "Căn cứ": r.reason,
                         "Hành động gợi ý": r.solution.actions} for r, u in recs])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame({"Thông tin": ["BÁO CÁO KẾT QUẢ ĐÁNH GIÁ CHUYỂN ĐỔI SỐ", f"Kỳ đánh giá: {p.name}",
                                    f"Ngày xuất: {date.today():%d/%m/%Y}", f"Người xuất: {user.full_name}",
                                    f"Số đơn vị: {len(df)}",
                                    f"DTI trung bình: {df['DTI'].mean():.2f}" if not df.empty else ""]}).to_excel(w, index=False, sheet_name="Tong_quan")
        df.to_excel(w, index=False, sheet_name="Xep_hang_don_vi")
        reg.to_excel(w, index=False, sheet_name="Theo_dia_ban")
        adf.to_excel(w, index=False, sheet_name="Canh_bao")
        rdf.to_excel(w, index=False, sheet_name="De_xuat_giai_phap")
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 2, 60)
    buf.seek(0)
    audit(db, user, "export", "report_dti", p.code, {"rows": len(df)}, request)
    db.commit()
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=bao_cao_DTI_{p.code}.xlsx"})



@router.get("/tasks.xlsx")
def export_tasks(request: Request, db: Session = Depends(get_db), user: User = Depends(require("report.export"))):
    """Báo cáo tiến độ thực hiện nhiệm vụ theo đơn vị (trong phạm vi)."""
    from ..models import Task, TaskAssignment
    scope = scoped_unit_ids(db, user)
    stmt = select(TaskAssignment, Task, Unit).join(Task, Task.id == TaskAssignment.task_id).join(Unit, Unit.id == TaskAssignment.unit_id)
    if scope is not None:
        stmt = stmt.where(or_(TaskAssignment.unit_id.in_(scope or [-1]), Task.assigner_unit_id.in_(scope or [-1])))
    rows = db.execute(stmt).all()
    today = date.today()
    detail = pd.DataFrame([{"Mã NV": t.code, "Trích yếu": t.title, "Cơ quan giao": t.assigner.name, "Đơn vị thực hiện": u.name,
                            "Địa bàn": u.region.name, "Hạn": t.deadline, "Trạng thái": a.status, "Tiến độ (%)": a.progress,
                            "Số đến": a.incoming_no, "Văn bản báo cáo": a.report_doc_number,
                            "Quá hạn": "Có" if a.status not in ("hoan_thanh", "khong_tiep_nhan") and t.deadline < today else "",
                            "Hoàn thành trễ": "Có" if a.status == "hoan_thanh" and a.confirmed_at and a.confirmed_at.date() > t.deadline else ""}
                           for a, t, u in rows])
    summ = pd.DataFrame()
    if not detail.empty:
        g = detail.groupby("Đơn vị thực hiện")
        summ = pd.DataFrame({"Số lượt giao": g.size(), "Hoàn thành": g.apply(lambda x: (x["Trạng thái"] == "hoan_thanh").sum()),
                             "Quá hạn": g.apply(lambda x: (x["Quá hạn"] == "Có").sum()),
                             "Hoàn thành trễ": g.apply(lambda x: (x["Hoàn thành trễ"] == "Có").sum())}).reset_index()
        summ["Tỷ lệ hoàn thành (%)"] = (summ["Hoàn thành"] * 100 / summ["Số lượt giao"]).round(1)
        summ = summ.sort_values("Tỷ lệ hoàn thành (%)")
    from .admin_ops import xlsx_response
    audit(db, user, "export", "report_tasks", None, {"rows": len(detail)}, request)
    db.commit()
    return xlsx_response({"tong_hop_don_vi": summ, "chi_tiet": detail}, f"bao_cao_nhiem_vu_{today:%Y%m%d}.xlsx")


@router.get("/trend.xlsx")
def export_trend(request: Request, unit_type: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("report.export"))):
    """Báo cáo diễn biến DTI theo thời gian: đơn vị × kỳ và địa bàn × kỳ."""
    from ..models import Period
    scope = scoped_unit_ids(db, user)
    stmt = apply_scope(select(Unit, Period.code, DTIScore.score).join(DTIScore, DTIScore.unit_id == Unit.id)
                       .join(Period, Period.id == DTIScore.period_id), Unit.id, scope)
    if unit_type:
        stmt = stmt.where(Unit.unit_type == unit_type)
    rows = db.execute(stmt).all()
    df = pd.DataFrame([{"Mã": u.code, "Đơn vị": u.name, "Địa bàn": u.region.name, "Kỳ": k, "DTI": s} for u, k, s in rows])
    sheets = {}
    if not df.empty:
        piv = df.pivot_table(index=["Mã", "Đơn vị", "Địa bàn"], columns="Kỳ", values="DTI").round(1).reset_index()
        ks = sorted(df["Kỳ"].unique())
        if len(ks) >= 2:
            piv["Tăng/giảm cả giai đoạn"] = (piv[ks[-1]] - piv[ks[0]]).round(1)
        sheets["don_vi_theo_ky"] = piv
        sheets["dia_ban_theo_ky"] = df.pivot_table(index="Địa bàn", columns="Kỳ", values="DTI", aggfunc="mean").round(1).reset_index()
        sheets["toan_pham_vi"] = df.groupby("Kỳ")["DTI"].agg(["count", "mean", "min", "max"]).round(1).reset_index() \
            .rename(columns={"count": "Số đơn vị", "mean": "DTI TB", "min": "Thấp nhất", "max": "Cao nhất"})
    from .admin_ops import xlsx_response
    audit(db, user, "export", "report_trend", None, {"rows": len(df)}, request)
    db.commit()
    return xlsx_response(sheets or {"trong": pd.DataFrame()}, f"bao_cao_dien_bien_DTI_{date.today():%Y%m%d}.xlsx")
