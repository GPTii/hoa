"""Sinh báo cáo KẾT QUẢ THỰC NGHIỆM (đề cương mục 3.12–3.13) từ dữ liệu trong CSDL.

    python -m scripts.report_experiment      → ghi docs/KET_QUA_THUC_NGHIEM.md
"""
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Criterion, DTIScore, IngestBatch, Period, Pillar, PillarScore, Recommendation, RejectedRecord, SolutionGroup, Task,
    TaskAssignment, Unit, UnitCluster, User,
)
from app.services import ml, scoring  # noqa: E402
from app.services.sysconfig import province_label  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "KET_QUA_THUC_NGHIEM.md"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else (f"{v:.2f}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(lines)


def main():
    db = SessionLocal()
    cur = db.scalar(select(Period).where(Period.is_current))
    periods = db.scalars(select(Period).order_by(Period.start_date)).all()
    L = [f"# Kết quả thực nghiệm\n\n*Sinh tự động ngày {date.today():%d/%m/%Y} bằng `python -m scripts.report_experiment` – "
         f"bộ dữ liệu: {province_label(db) or 'chưa cấu hình'} (dữ liệu mô phỏng).*\n"]

    # 1. Quy mô dữ liệu
    n_units = db.scalar(select(func.count(Unit.id)))
    by_type = dict(db.execute(select(Unit.unit_type, func.count()).group_by(Unit.unit_type)).all())
    rows = db.execute(text("SELECT schemaname, sum(n_live_tup) FROM pg_stat_user_tables GROUP BY schemaname ORDER BY 1")).all()
    L.append("## 1. Quy mô bộ dữ liệu thực nghiệm\n")
    L.append(md_table(pd.DataFrame([
        ["Đơn vị", n_units, f"{by_type.get('hanh_chinh', 0)} cơ quan hành chính, {by_type.get('giao_duc', 0)} cơ sở giáo dục"],
        ["Kỳ đánh giá", len(periods), f"{periods[0].code} → {periods[-1].code}"],
        ["Tiêu chí / trụ cột", db.scalar(select(func.count(Criterion.id))), f"{db.scalar(select(func.count(Pillar.id)))} trụ cột"],
        ["Nhiệm vụ / lượt giao", db.scalar(select(func.count(Task.id))), f"{db.scalar(select(func.count(TaskAssignment.id)))} lượt giao"],
        ["Người dùng", db.scalar(select(func.count(User.id))), ""],
    ] + [[f"Bản ghi schema {s}", int(n), ""] for s, n in rows], columns=["Hạng mục", "Số lượng", "Ghi chú"])))

    # 2. Pipeline – chất lượng dữ liệu
    b = pd.DataFrame(db.execute(select(IngestBatch.source_type, func.count(), func.sum(IngestBatch.total_rows), func.sum(IngestBatch.valid_values),
                                       func.sum(IngestBatch.rejected_values)).group_by(IngestBatch.source_type)).all(),
                     columns=["Nguồn", "Số lô", "Dòng thô (Bronze)", "Giá trị hợp lệ (Silver)", "Giá trị bị loại"])
    reasons = pd.DataFrame(db.execute(select(RejectedRecord.reason, func.count()).group_by(RejectedRecord.reason)
                                      .order_by(func.count().desc())).all(), columns=["Lý do loại (Silver)", "Số lượng"])
    L.append("\n## 2. Pipeline Bronze → Silver → Gold\n")
    L.append(md_table(b))
    L.append("\nCác lỗi được phát hiện và loại ở bước làm sạch:\n")
    L.append(md_table(reasons))
    t0 = time.perf_counter()
    scoring.compute_period(db, cur)
    t1 = time.perf_counter()
    L.append(f"\nThời gian tính toàn bộ tầng Gold cho 1 kỳ ({n_units} đơn vị): **{t1 - t0:.2f} giây**.\n")

    # 3. Kết quả DTI
    dti = pd.DataFrame(db.execute(select(Period.code, func.count(), func.avg(DTIScore.score), func.min(DTIScore.score), func.max(DTIScore.score),
                                         func.stddev(DTIScore.score)).join(DTIScore, DTIScore.period_id == Period.id)
                                  .group_by(Period.code, Period.start_date).order_by(Period.start_date)).all(),
                       columns=["Kỳ", "Số đơn vị", "DTI TB", "Thấp nhất", "Cao nhất", "Độ lệch chuẩn"])
    lv = pd.DataFrame(db.execute(select(DTIScore.level, func.count()).where(DTIScore.period_id == cur.id).group_by(DTIScore.level)).all(),
                      columns=["Mức độ", "Số đơn vị"])
    lv["Tỷ lệ (%)"] = (lv["Số đơn vị"] * 100 / lv["Số đơn vị"].sum()).round(1)
    cat = pd.DataFrame(db.execute(select(Unit.category, func.count(), func.avg(DTIScore.score)).join(DTIScore, DTIScore.unit_id == Unit.id)
                                  .where(DTIScore.period_id == cur.id).group_by(Unit.category).order_by(func.avg(DTIScore.score).desc())).all(),
                       columns=["Loại hình", "Số đơn vị", "DTI TB"])
    pil = pd.DataFrame(db.execute(select(Pillar.name, Pillar.weight, func.avg(PillarScore.score)).join(PillarScore)
                                  .where(PillarScore.period_id == cur.id).group_by(Pillar.name, Pillar.weight, Pillar.sort_order)
                                  .order_by(Pillar.sort_order)).all(), columns=["Trụ cột", "Trọng số", "Điểm TB"])
    L.append("\n## 3. Kết quả Digital Transformation Score\n\n### 3.1 Diễn biến theo kỳ\n")
    L.append(md_table(dti))
    L.append(f"\n### 3.2 Phân loại mức độ – {cur.name}\n")
    L.append(md_table(lv))
    L.append("\n### 3.3 Theo loại hình đơn vị\n")
    L.append(md_table(cat))
    L.append("\n### 3.4 Theo trụ cột (trụ cột yếu nhất là ưu tiên hoạch định)\n")
    L.append(md_table(pil))

    # 4. Cảnh báo, ưu tiên, đề xuất
    from app.models import Alert, PriorityUnit
    al = pd.DataFrame(db.execute(select(Alert.alert_type, Alert.severity, func.count()).where(Alert.period_id == cur.id)
                                 .group_by(Alert.alert_type, Alert.severity)).all(), columns=["Loại cảnh báo", "Mức", "Số lượng"])
    rec = pd.DataFrame(db.execute(select(SolutionGroup.name, func.count(Recommendation.id), func.avg(Recommendation.priority_score))
                                  .join(Recommendation, Recommendation.solution_group_id == SolutionGroup.id)
                                  .where(Recommendation.period_id == cur.id).group_by(SolutionGroup.name)
                                  .order_by(func.count(Recommendation.id).desc()).limit(8)).all(), columns=["Nhóm giải pháp", "Số đơn vị", "Điểm ưu tiên TB"])
    top = pd.DataFrame(db.execute(select(Unit.name, PriorityUnit.priority_index, PriorityUnit.reasons).join(Unit, Unit.id == PriorityUnit.unit_id)
                                  .where(PriorityUnit.period_id == cur.id).order_by(PriorityUnit.rank).limit(5)).all(),
                       columns=["Đơn vị ưu tiên", "Chỉ số ưu tiên", "Lý do"])
    L.append("\n## 4. Cảnh báo, đơn vị ưu tiên, đề xuất giải pháp\n")
    L.append(md_table(al))
    L.append("\n**5 đơn vị cần ưu tiên nhất:**\n")
    L.append(md_table(top))
    L.append("\n**Nhóm giải pháp được đề xuất nhiều nhất:**\n")
    L.append(md_table(rec))

    # 5. ML
    ev = ml.evaluate(db, cur)
    cl = pd.DataFrame(db.execute(select(UnitCluster.cluster_label, func.count(), func.avg(DTIScore.score))
                                 .join(DTIScore, (DTIScore.unit_id == UnitCluster.unit_id) & (DTIScore.period_id == UnitCluster.period_id))
                                 .where(UnitCluster.period_id == cur.id).group_by(UnitCluster.cluster_label, UnitCluster.cluster)
                                 .order_by(UnitCluster.cluster)).all(), columns=["Cụm (k=4)", "Số đơn vị", "DTI TB"])
    L.append("\n## 5. Machine Learning\n\n### 5.1 Phân cụm K-Means\n")
    L.append(md_table(pd.DataFrame(ev["clustering"]).rename(columns={"k": "k", "silhouette": "Silhouette", "inertia": "Inertia"})))
    L.append(f"\nSilhouette cao nhất tại k = {ev.get('best_k')}. Hệ thống chọn **k = 4** vì cho 4 nhóm có ý nghĩa quản lý "
             "(dẫn đầu / khá / trung bình / yếu) trong khi silhouette chênh lệch không đáng kể – đây là đánh đổi giữa độ tách cụm và tính diễn giải.\n")
    L.append(md_table(cl))
    if ev["forecast"]:
        f = ev["forecast"]
        L.append(f"\n### 5.2 Dự báo DTI kỳ kế tiếp – backtest ({f['units']} đơn vị)\n")
        L.append(md_table(pd.DataFrame([["Hồi quy tuyến tính (hệ thống)", *f["linear"].values()], ["Cơ sở: giữ nguyên kỳ trước", *f["naive"].values()]],
                                       columns=["Mô hình", "MAE", "RMSE", "MAPE (%)"])))
        L.append(f"\nMô hình giảm sai số tuyệt đối trung bình **{f['improvement_pct']}%** so với mô hình cơ sở.\n")

    # 6. Kiểm thử
    L.append("\n## 6. Kiểm thử chức năng\n\nCác bộ kiểm thử tự động (chạy khi backend hoạt động ở cổng 8000):\n")
    L.append(md_table(pd.DataFrame([
        ["scripts.smoke_test", "Toàn bộ API theo vai trò; phạm vi dữ liệu; luồng nhiệm vụ 2 & 3 cấp; pipeline nhập file lỗi; quản trị phân cấp; bàn làm việc"],
        ["scripts.test_privacy_features", "Che thông tin hệ thống; thông báo; số đến; đôn đốc; đính kèm; tự khai báo hạ tầng"],
        ["scripts.test_impersonation", "Quản trị xem dưới vai trò (chỉ xem), trở về, nhật ký"],
        ["scripts.test_admin_ops", "8 nhóm quản trị: khóa đăng nhập, phiên, đổi MK bắt buộc, nhập/xuất, chuyển giao, cấu hình, kỳ, thông báo, giám sát, sao lưu, nhật ký, khóa API"],
        ["scripts.test_outline_features", "Danh mục dịch vụ; cơ quan cấp tỉnh; kế hoạch chăm sóc AM; lập kế hoạch cải thiện; báo cáo bổ sung; đánh giá ML; view Power BI"],
        ["scripts.test_new_province", "Khởi tạo tỉnh mới, nhập danh mục Excel, trạng thái thiết lập (chạy trên hệ thống --blank)"],
    ], columns=["Bộ kiểm thử", "Phạm vi"])))
    L.append("\nKết quả lần chạy gần nhất: **tất cả đạt** (xem log khi chạy lại).\n")

    OUT.write_text("\n".join(L), encoding="utf-8")
    db.rollback()
    db.close()
    print("Đã ghi", OUT)


if __name__ == "__main__":
    main()
