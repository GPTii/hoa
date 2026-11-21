"""Mô hình dữ liệu của nền tảng.

- Schema `public`  : dữ liệu nghiệp vụ (OLTP) – danh mục, đơn vị, người dùng, nhiệm vụ...
- Schema `bronze`  : dữ liệu thô tiếp nhận nguyên trạng (lô nhập, bản ghi JSONB).
- Schema `silver`  : dữ liệu đã làm sạch, chuẩn hóa về dạng dài (đơn vị – kỳ – tiêu chí – giá trị).
- Schema `gold`    : dữ liệu phân tích – điểm tiêu chí, trụ cột, DTI, cảnh báo, đề xuất, phân cụm.
"""
from datetime import date, datetime

from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Table, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# ---------------------------------------------------------------- public: danh mục & tổ chức


class Region(Base):
    """Địa bàn theo mô hình chính quyền 2 cấp: Tỉnh → Xã / Phường / Đặc khu."""
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))  # tinh | phuong | xa | dac_khu
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    population: Mapped[int | None] = mapped_column(Integer)
    area_km2: Mapped[float | None] = mapped_column(Float)


class Unit(Base):
    """Đơn vị: cơ quan hành chính (UBND tỉnh, Sở, UBND xã...) hoặc cơ sở giáo dục."""
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    unit_type: Mapped[str] = mapped_column(String(20))  # hanh_chinh | giao_duc
    category: Mapped[str] = mapped_column(String(30))  # ubnd_tinh | van_phong | so_nganh | ubnd_xa | thpt | thcs | tieu_hoc | mam_non
    level: Mapped[str] = mapped_column(String(10))  # tinh | xa
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    parent_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    address: Mapped[str | None] = mapped_column(String(255))
    head_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    staff_count: Mapped[int | None] = mapped_column(Integer)
    student_count: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    region: Mapped[Region] = relationship()


role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(60))


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    # Phạm vi dữ liệu: all = toàn tỉnh | region = theo xã/phường | unit = chỉ đơn vị mình | assigned = đơn vị được phân công (AM)
    data_scope: Mapped[str] = mapped_column(String(20), default="unit")
    level: Mapped[str] = mapped_column(String(20), default="khac")  # he_thong | tinh | so | xa | truong | khac
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    duties: Mapped[str | None] = mapped_column(Text)  # mô tả công việc chính, phân tách bằng '|'
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    position: Mapped[str | None] = mapped_column(String(120))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)       # khóa tạm do đăng nhập sai nhiều lần
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role: Mapped[Role] = relationship(lazy="joined")
    unit: Mapped[Unit | None] = relationship(lazy="joined")
    region: Mapped[Region | None] = relationship(lazy="joined")


class AMAssignment(Base):
    """Phân công nhân viên phụ trách (AM) chăm sóc đơn vị."""
    __tablename__ = "am_assignments"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------- public: hạ tầng & dịch vụ số


class ServiceCatalog(Base):
    """Danh mục dịch vụ / giải pháp công nghệ (VBĐH, DVC, chữ ký số, sổ liên lạc điện tử...)."""
    __tablename__ = "service_catalog"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(100), default="VNPT")
    category: Mapped[str] = mapped_column(String(40))
    pillar_code: Mapped[str | None] = mapped_column(String(20))
    unit_types: Mapped[list[str]] = mapped_column(ARRAY(String))
    monthly_price: Mapped[float] = mapped_column(Numeric(14, 0), default=0)
    description: Mapped[str | None] = mapped_column(Text)


class UnitService(Base):
    __tablename__ = "unit_services"
    __table_args__ = (UniqueConstraint("unit_id", "service_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    service_id: Mapped[int] = mapped_column(ForeignKey("service_catalog.id"))
    status: Mapped[str] = mapped_column(String(20))  # dang_dung | dung_thu | het_han | ngung
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    usage_level: Mapped[int] = mapped_column(Integer, default=0)  # 0-100: mức độ khai thác
    monthly_fee: Mapped[float] = mapped_column(Numeric(14, 0), default=0)
    note: Mapped[str | None] = mapped_column(Text)
    service: Mapped[ServiceCatalog] = relationship(lazy="joined")


class UnitInfra(Base):
    __tablename__ = "unit_infra"
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    computers: Mapped[int] = mapped_column(Integer, default=0)
    servers: Mapped[int] = mapped_column(Integer, default=0)
    internet_mbps: Mapped[int] = mapped_column(Integer, default=0)
    has_lan: Mapped[bool] = mapped_column(Boolean, default=False)
    has_wifi: Mapped[bool] = mapped_column(Boolean, default=False)
    has_firewall: Mapped[bool] = mapped_column(Boolean, default=False)
    has_backup: Mapped[bool] = mapped_column(Boolean, default=False)
    has_camera: Mapped[bool] = mapped_column(Boolean, default=False)
    smart_classrooms: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------- public: bộ tiêu chí đánh giá


class Period(Base):
    __tablename__ = "periods"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)  # 2026-Q3
    name: Mapped[str] = mapped_column(String(60))
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)   # UBND tỉnh công bố kết quả chính thức
    published_by: Mapped[str | None] = mapped_column(String(120))
    publish_decision: Mapped[str | None] = mapped_column(String(80))  # số quyết định công bố  # khóa số liệu: không nhận dữ liệu mới, không tính lại


class Pillar(Base):
    """Trụ cột (nhóm tiêu chí) của chỉ số chuyển đổi số."""
    __tablename__ = "pillars"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)  # tổng các trụ cột = 100
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Criterion(Base):
    __tablename__ = "criteria"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    pillar_id: Mapped[int] = mapped_column(ForeignKey("pillars.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    unit_type: Mapped[str] = mapped_column(String(20), default="all")  # all | hanh_chinh | giao_duc
    metric_type: Mapped[str] = mapped_column(String(20))  # ratio | boolean | number
    target: Mapped[float] = mapped_column(Float, default=100)  # giá trị đạt 100 điểm
    weight: Mapped[float] = mapped_column(Float, default=1)  # trọng số trong trụ cột
    unit_label: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(20), default="survey")  # survey | tasks | services | infra
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    pillar: Mapped[Pillar] = relationship(lazy="joined")


class SolutionGroup(Base):
    """Nhóm giải pháp chuyển đổi số tham khảo – dùng cho chức năng đề xuất/hoạch định."""
    __tablename__ = "solution_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    pillar_id: Mapped[int] = mapped_column(ForeignKey("pillars.id"))
    trigger_criteria: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    unit_type: Mapped[str] = mapped_column(String(20), default="all")
    description: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[str | None] = mapped_column(Text)
    service_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    cost_level: Mapped[str] = mapped_column(String(20), default="trung_binh")  # thap | trung_binh | cao
    duration_months: Mapped[int] = mapped_column(Integer, default=3)
    pillar: Mapped[Pillar] = relationship(lazy="joined")


# ---------------------------------------------------------------- public: giao & theo dõi nhiệm vụ (liên thông VBĐH)


class Task(Base):
    """Nhiệm vụ được giao kèm văn bản chỉ đạo (UBND tỉnh / Sở → UBND xã, phường, trường học)."""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str | None] = mapped_column(Text)
    doc_number: Mapped[str | None] = mapped_column(String(60))  # Số/ký hiệu văn bản giao
    doc_date: Mapped[date | None] = mapped_column(Date)
    doc_type: Mapped[str] = mapped_column(String(30), default="cong_van")
    assigner_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    priority: Mapped[str] = mapped_column(String(10), default="thuong")  # thuong | khan
    require_report: Mapped[bool] = mapped_column(Boolean, default=True)
    deadline: Mapped[date] = mapped_column(Date)
    pillar_code: Mapped[str | None] = mapped_column(String(20))
    # Giao tiếp nhiều cấp: nhiệm vụ con sinh ra từ lượt giao của cấp trên (Tỉnh → Xã → Trường)
    parent_assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_assignments.id", ondelete="CASCADE", use_alter=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    assigner: Mapped[Unit] = relationship(lazy="joined")
    assignments: Mapped[list["TaskAssignment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin", foreign_keys="TaskAssignment.task_id")


class TaskAssignment(Base):
    """Trạng thái xử lý nhiệm vụ tại từng đơn vị nhận (chủ trì / phối hợp).

    Vòng đời: chua_tiep_nhan → (khong_tiep_nhan) | dang_xu_ly → da_bao_cao → hoan_thanh | tra_lai → dang_xu_ly ...
    Lưu ý nghiệp vụ: đơn vị đã nhận văn bản ≠ đã hoàn thành; đã gửi báo cáo ≠ hoàn thành.
    Chỉ cơ quan giao nhiệm vụ xác nhận mới chuyển sang `hoan_thanh`.
    """
    __tablename__ = "task_assignments"
    __table_args__ = (UniqueConstraint("task_id", "unit_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    role: Mapped[str] = mapped_column(String(10), default="chu_tri")  # chu_tri | phoi_hop
    status: Mapped[str] = mapped_column(String(20), default="chua_tiep_nhan")
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    handler_dept: Mapped[str | None] = mapped_column(String(120))
    handler_name: Mapped[str | None] = mapped_column(String(120))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    incoming_no: Mapped[int | None] = mapped_column(Integer)  # số đến trong sổ văn bản đến của đơn vị (theo năm)
    leader_opinion: Mapped[str | None] = mapped_column(Text)   # ý kiến chỉ đạo (bút phê) của lãnh đạo khi phân công
    reviewed_by: Mapped[str | None] = mapped_column(String(120))  # trưởng phòng kiểm tra dự thảo
    signed_by: Mapped[str | None] = mapped_column(String(120))    # người ký văn bản báo cáo
    signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    outgoing_no: Mapped[int | None] = mapped_column(Integer)      # số văn bản đi do văn thư cấp (theo năm)
    issued_by: Mapped[str | None] = mapped_column(String(120))    # văn thư phát hành
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    report_doc_number: Mapped[str | None] = mapped_column(String(60))
    report_note: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(Text)
    task: Mapped[Task] = relationship(back_populates="assignments", foreign_keys=[task_id])
    unit: Mapped[Unit] = relationship(lazy="joined")


class TaskLog(Base):
    __tablename__ = "task_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("task_assignments.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaskAttachment(Base):
    """Tệp đính kèm: văn bản giao (của cơ quan giao) hoặc báo cáo kết quả (của đơn vị nhận)."""
    __tablename__ = "task_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("task_assignments.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20), default="van_ban")  # van_ban | bao_cao
    file_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Notification(Base):
    """Thông báo / nhắc việc gửi tới từng người dùng."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # van_ban_den | phan_cong | trinh | bao_cao | ket_qua | don_doc | he_thong
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Assessment(Base):
    """Phiếu TỰ ĐÁNH GIÁ mức độ chuyển đổi số của đơn vị trong một kỳ.
    Vòng đời: nhap → da_nop → (tra_lai → da_nop …) → da_tham_dinh. Chuyên viên/giáo viên khai, lãnh đạo duyệt nộp,
    cơ quan thẩm định (Sở KH&CN; Sở GD&ĐT với trường học) chấp nhận hoặc điều chỉnh từng tiêu chí rồi phê duyệt."""
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("unit_id", "period_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="nhap")
    prepared_by: Mapped[str | None] = mapped_column(String(120))
    submitted_by: Mapped[str | None] = mapped_column(String(120))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(Text)
    self_score: Mapped[float | None] = mapped_column(Float)    # điểm tự chấm (ước tính)
    final_score: Mapped[float | None] = mapped_column(Float)   # điểm sau thẩm định
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("bronze.ingest_batches.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    unit: Mapped[Unit] = relationship(lazy="joined")
    items: Mapped[list["AssessmentItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="AssessmentItem.id")


class AssessmentItem(Base):
    __tablename__ = "assessment_items"
    __table_args__ = (UniqueConstraint("assessment_id", "criterion_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id"))
    value_raw: Mapped[str | None] = mapped_column(String(100))      # giá trị đơn vị tự khai
    evidence: Mapped[str | None] = mapped_column(Text)              # minh chứng (số văn bản, đường dẫn, mô tả)
    reviewer_value: Mapped[str | None] = mapped_column(String(100)) # giá trị sau thẩm định (trống = chấp nhận)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    criterion: Mapped["Criterion"] = relationship(lazy="joined")


class CarePlan(Base):
    """Kế hoạch chăm sóc đơn vị của nhân viên AM (tư vấn, tập huấn, gia hạn, triển khai dịch vụ...)."""
    __tablename__ = "care_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    am_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    activity: Mapped[str] = mapped_column(String(20))  # tu_van | tap_huan | gia_han | trien_khai | khao_sat | ho_tro
    title: Mapped[str] = mapped_column(String(300))
    service_code: Mapped[str | None] = mapped_column(String(40))
    planned_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="ke_hoach")  # ke_hoach | da_thuc_hien | huy
    note: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImprovementPlan(Base):
    """Kế hoạch cải thiện chuyển đổi số lập từ đề xuất của hệ thống (cho một đơn vị hoặc một địa bàn)."""
    __tablename__ = "improvement_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    scope: Mapped[str] = mapped_column(String(10))  # unit | region | tinh
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"))
    owner_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    status: Mapped[str] = mapped_column(String(20), default="du_thao")  # du_thao | ban_hanh | hoan_thanh
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    items: Mapped[list["PlanItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="PlanItem.id")


class PlanItem(Base):
    __tablename__ = "plan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("improvement_plans.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    solution_group_id: Mapped[int | None] = mapped_column(ForeignKey("solution_groups.id"))
    action: Mapped[str] = mapped_column(Text)
    responsible: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(10), default="trung_binh")
    cost_level: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="chua_lam")  # chua_lam | dang_lam | hoan_thanh
    progress: Mapped[int] = mapped_column(Integer, default=0)
    baseline_score: Mapped[float | None] = mapped_column(Float)  # điểm trung bình tiêu chí kích hoạt lúc lập kế hoạch
    unit: Mapped[Unit] = relationship(lazy="joined")
    solution: Mapped["SolutionGroup | None"] = relationship(lazy="joined")


class SystemSetting(Base):
    """Tham số hệ thống do quản trị cấu hình (chính sách mật khẩu, phiên, chế độ demo...)."""
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | str | int | bool | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(60))


class UserSession(Base):
    """Phiên đăng nhập – cho phép xem thiết bị/IP đang đăng nhập và buộc đăng xuất từ xa."""
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    imp_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ip: Mapped[str | None] = mapped_column(String(60))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_reason: Mapped[str | None] = mapped_column(String(120))


class Announcement(Base):
    """Thông báo hệ thống (bảo trì, hướng dẫn) gửi theo cấp."""
    __tablename__ = "announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str] = mapped_column(String(20), default="all")  # all | tinh | so | xa | truong | khac
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info | warning | critical
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApiKey(Base):
    """Khóa API cho hệ thống ngoài (LGSP, VBĐH) – chỉ lưu băm, hiển thị khóa gốc 1 lần khi tạo."""
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(128))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_by: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class BackupRecord(Base):
    __tablename__ = "backups"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20))  # thanh_cong | loi
    message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApiError(Base):
    """Lỗi máy chủ (HTTP 5xx) ghi lại để giám sát."""
    __tablename__ = "api_errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(300))
    status: Mapped[int] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    username: Mapped[str | None] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------- bronze


class IngestBatch(Base):
    __tablename__ = "ingest_batches"
    __table_args__ = {"schema": "bronze"}
    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(30))  # upload_csv | upload_xlsx | tasks_sync | services_sync | seed
    file_name: Mapped[str | None] = mapped_column(String(255))
    period_code: Mapped[str | None] = mapped_column(String(10))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="bronze")  # bronze | silver | gold | failed
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_values: Mapped[int] = mapped_column(Integer, default=0)
    rejected_values: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = {"schema": "bronze"}
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("bronze.ingest_batches.id", ondelete="CASCADE"), index=True)
    row_no: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)


# ---------------------------------------------------------------- silver


class UnitMetric(Base):
    __tablename__ = "unit_metrics"
    __table_args__ = (UniqueConstraint("unit_id", "period_id", "criterion_id"), {"schema": "silver"})
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("bronze.ingest_batches.id", ondelete="SET NULL"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id"))
    raw_value: Mapped[str | None] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RejectedRecord(Base):
    __tablename__ = "rejected_records"
    __table_args__ = {"schema": "silver"}
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("bronze.ingest_batches.id", ondelete="CASCADE"), index=True)
    row_no: Mapped[int] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(60))
    raw_value: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(String(255))


# ---------------------------------------------------------------- gold


class CriterionScore(Base):
    __tablename__ = "criterion_scores"
    __table_args__ = {"schema": "gold"}
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), primary_key=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id"), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)


class PillarScore(Base):
    __tablename__ = "pillar_scores"
    __table_args__ = {"schema": "gold"}
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), primary_key=True)
    pillar_id: Mapped[int] = mapped_column(ForeignKey("pillars.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float)


class DTIScore(Base):
    __tablename__ = "dti_scores"
    __table_args__ = {"schema": "gold"}
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(20))
    rank_overall: Mapped[int | None] = mapped_column(Integer)
    rank_in_group: Mapped[int | None] = mapped_column(Integer)
    delta_prev: Mapped[float | None] = mapped_column(Float)
    completeness: Mapped[float] = mapped_column(Float, default=100)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RegionScore(Base):
    __tablename__ = "region_scores"
    __table_args__ = {"schema": "gold"}
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), primary_key=True)
    avg_score: Mapped[float] = mapped_column(Float)
    admin_avg: Mapped[float | None] = mapped_column(Float)
    edu_avg: Mapped[float | None] = mapped_column(Float)
    unit_count: Mapped[int] = mapped_column(Integer)
    min_score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = {"schema": "gold"}
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(30))  # LOW_SCORE | SCORE_DROP | WEAK_PILLAR | OVERDUE_TASK | MISSING_DATA | EXPIRING_SERVICE
    severity: Mapped[str] = mapped_column(String(10))  # cao | trung_binh | thap
    message: Mapped[str] = mapped_column(Text)
    metric_value: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = {"schema": "gold"}
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    solution_group_id: Mapped[int] = mapped_column(ForeignKey("solution_groups.id"))
    priority_score: Mapped[float] = mapped_column(Float)
    priority_level: Mapped[str] = mapped_column(String(10))  # cao | trung_binh | thap
    reason: Mapped[str] = mapped_column(Text)
    missing_services: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    solution: Mapped[SolutionGroup] = relationship(lazy="joined")


class PriorityUnit(Base):
    __tablename__ = "priority_units"
    __table_args__ = {"schema": "gold"}
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), primary_key=True)
    priority_index: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[str] = mapped_column(Text)


class UnitCluster(Base):
    __tablename__ = "unit_clusters"
    __table_args__ = {"schema": "gold"}
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), primary_key=True)
    cluster: Mapped[int] = mapped_column(Integer)
    cluster_label: Mapped[str] = mapped_column(String(80))
    forecast_next: Mapped[float | None] = mapped_column(Float)
    trend_slope: Mapped[float | None] = mapped_column(Float)
