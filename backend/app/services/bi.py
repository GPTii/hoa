"""Tầng dữ liệu cho công cụ BI ngoài (Power BI, Excel PivotTable, Metabase…) – đề cương mục 4.4.

Các view phẳng trong schema `gold`, tên cột tiếng Việt không dấu, chỉ đọc. Power BI kết nối PostgreSQL bằng tài khoản
chỉ đọc (xem docs/HUONG_DAN_POWER_BI.md) rồi chọn các view `gold.v_bi_*`.
"""
from sqlalchemy import text

VIEWS = {
    "v_bi_dti": """
        SELECT p.code AS ky, p.year AS nam, p.quarter AS quy, u.code AS ma_don_vi, u.name AS ten_don_vi,
               u.unit_type AS loai_hinh, u.category AS phan_loai, u.level AS cap, r.code AS ma_dia_ban, r.name AS dia_ban,
               d.score AS diem_dti, d.level AS muc_do, d.rank_overall AS hang, d.delta_prev AS tang_giam, d.completeness AS do_day_du
        FROM gold.dti_scores d JOIN public.periods p ON p.id = d.period_id
        JOIN public.units u ON u.id = d.unit_id JOIN public.regions r ON r.id = u.region_id""",
    "v_bi_tru_cot": """
        SELECT p.code AS ky, u.code AS ma_don_vi, u.name AS ten_don_vi, r.name AS dia_ban, u.unit_type AS loai_hinh,
               pl.code AS ma_tru_cot, pl.name AS tru_cot, pl.weight AS trong_so, s.score AS diem
        FROM gold.pillar_scores s JOIN public.periods p ON p.id = s.period_id JOIN public.pillars pl ON pl.id = s.pillar_id
        JOIN public.units u ON u.id = s.unit_id JOIN public.regions r ON r.id = u.region_id""",
    "v_bi_tieu_chi": """
        SELECT p.code AS ky, u.code AS ma_don_vi, r.name AS dia_ban, c.code AS ma_tieu_chi, c.name AS tieu_chi,
               pl.name AS tru_cot, cs.value AS gia_tri, cs.score AS diem
        FROM gold.criterion_scores cs JOIN public.periods p ON p.id = cs.period_id JOIN public.criteria c ON c.id = cs.criterion_id
        JOIN public.pillars pl ON pl.id = c.pillar_id JOIN public.units u ON u.id = cs.unit_id JOIN public.regions r ON r.id = u.region_id""",
    "v_bi_dia_ban": """
        SELECT p.code AS ky, r.code AS ma_dia_ban, r.name AS dia_ban, r.type AS loai, rs.avg_score AS dti_tb,
               rs.admin_avg AS dti_hanh_chinh, rs.edu_avg AS dti_giao_duc, rs.unit_count AS so_don_vi, rs.rank AS hang
        FROM gold.region_scores rs JOIN public.periods p ON p.id = rs.period_id JOIN public.regions r ON r.id = rs.region_id""",
    "v_bi_canh_bao": """
        SELECT p.code AS ky, u.code AS ma_don_vi, u.name AS ten_don_vi, r.name AS dia_ban, a.alert_type AS loai,
               a.severity AS muc_do, a.message AS noi_dung
        FROM gold.alerts a JOIN public.periods p ON p.id = a.period_id JOIN public.units u ON u.id = a.unit_id
        JOIN public.regions r ON r.id = u.region_id""",
    "v_bi_nhiem_vu": """
        SELECT t.code AS ma_nhiem_vu, t.title AS trich_yeu, ua.name AS co_quan_giao, u.name AS don_vi_thuc_hien, r.name AS dia_ban,
               t.deadline AS han, a.status AS trang_thai, a.progress AS tien_do,
               (a.status NOT IN ('hoan_thanh','khong_tiep_nhan') AND t.deadline < CURRENT_DATE) AS qua_han
        FROM public.task_assignments a JOIN public.tasks t ON t.id = a.task_id JOIN public.units u ON u.id = a.unit_id
        JOIN public.units ua ON ua.id = t.assigner_unit_id JOIN public.regions r ON r.id = u.region_id""",
}


def create_bi_views(engine):
    with engine.begin() as c:
        for name, sql in VIEWS.items():
            c.execute(text(f"CREATE OR REPLACE VIEW gold.{name} AS {sql}"))
