"""Chức năng vận hành dành cho quản trị hệ thống (không chạm số liệu nghiệp vụ):

1. Bảo mật tài khoản: mở khóa, phiên đăng nhập, buộc đăng xuất
2. Nhập / xuất tài khoản hàng loạt, tài khoản không hoạt động, khóa hàng loạt
3. Chuyển giao công việc khi cán bộ nghỉ / chuyển công tác
4. Cấu hình: tham số hệ thống, kỳ đánh giá, danh mục địa bàn
5. Thông báo hệ thống theo cấp
6. Giám sát hệ thống & sao lưu CSDL
7. Nhật ký nâng cao: lọc thời gian, xuất Excel, cảnh báo bảo mật
8. Khóa API cho hệ thống tích hợp
"""
import hashlib
import io
import os
import secrets
import shutil
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import (
    AMAssignment, Announcement, ApiError, ApiKey, AuditLog, BackupRecord, Notification, Period, Region, Role, TaskAssignment,
    TaskLog, Unit, User, UserSession,
)
from ..security import audit, hash_password, require
from ..services.sysconfig import all_settings, get_setting, set_setting
from .admin import admin_user_out, assignable_roles, ensure_manageable, is_super, managed_unit_ids
from .auth import LEVEL_NAMES

router = APIRouter(prefix="/api/admin", tags=["Quản trị – vận hành"])
STARTED = time.time()
BACKUP_DIR = Path(__file__).resolve().parents[2] / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def need_super(me: User):
    if not is_super(me):
        raise HTTPException(403, "Chức năng dành cho quản trị hệ thống cấp tỉnh")


def xlsx_response(sheets: dict[str, pd.DataFrame], filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, index=False, sheet_name=name)
            ws = w.book[name]
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 2, 60)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


# ===================================================================== 1. bảo mật tài khoản


@router.post("/users/{uid}/unlock")
def unlock_user(uid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    ensure_manageable(db, me, u)
    u.failed_logins, u.locked_until = 0, None
    audit(db, me, "unlock_login", "user", uid, request=request)
    db.commit()
    return {"ok": True}


@router.post("/users/{uid}/revoke-sessions")
def revoke_user_sessions(uid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    ensure_manageable(db, me, u)
    n = db.execute(update(UserSession).where(UserSession.user_id == uid, ~UserSession.revoked)
                   .values(revoked=True, revoked_reason=f"Quản trị {me.username} buộc đăng xuất")).rowcount
    audit(db, me, "revoke_sessions", "user", uid, {"count": n}, request)
    db.commit()
    return {"revoked": n}


@router.get("/sessions")
def sessions(active_only: bool = True, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    stmt = select(UserSession, User).join(User, User.id == UserSession.user_id)
    if active_only:
        stmt = stmt.where(~UserSession.revoked, UserSession.expires_at > datetime.now())
    ids = managed_unit_ids(db, me)
    if ids is not None:
        stmt = stmt.where(User.unit_id.in_(ids or [-1]))
    rows = db.execute(stmt.order_by(UserSession.last_seen.desc()).limit(300)).all()
    imp_names = dict(db.execute(select(User.id, User.username)).all())
    return [{"id": s.id, "user_id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role.name,
             "ip": s.ip, "user_agent": s.user_agent, "created_at": s.created_at, "last_seen": s.last_seen,
             "expires_at": s.expires_at, "revoked": s.revoked, "revoked_reason": s.revoked_reason,
             "impersonated_by": imp_names.get(s.imp_by) if s.imp_by else None,
             "online": (datetime.now() - s.last_seen).total_seconds() < 300} for s, u in rows]


@router.post("/sessions/{sid}/revoke")
def revoke_session(sid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    s = db.get(UserSession, sid)
    if not s:
        raise HTTPException(404)
    ensure_manageable(db, me, db.get(User, s.user_id))
    if s.id == getattr(me, "session_id", None):
        raise HTTPException(400, "Không thể thu hồi phiên bạn đang dùng – hãy đăng xuất")
    s.revoked, s.revoked_reason = True, f"Quản trị {me.username} buộc đăng xuất"
    audit(db, me, "revoke_session", "session", sid, {"user_id": s.user_id}, request)
    db.commit()
    return {"ok": True}


# ===================================================================== 2. nhập / xuất hàng loạt

IMPORT_COLS = ["ten_dang_nhap", "ho_ten", "ma_vai_tro", "ma_don_vi", "chuc_vu", "email", "dien_thoai"]


@router.get("/users/template.xlsx")
def import_template(db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    roles = assignable_roles(db, me)
    ids = managed_unit_ids(db, me)
    units = db.scalars(select(Unit).where(Unit.id.in_(ids or [-1])) if ids is not None else select(Unit)).all()
    sample = pd.DataFrame([{"ten_dang_nhap": "vanthu.xa_moi", "ho_ten": "Nguyễn Văn A", "ma_vai_tro": "van_thu_xa",
                            "ma_don_vi": next((u.code for u in units if u.category == "ubnd_xa"), units[0].code if units else ""),
                            "chuc_vu": "Văn thư", "email": "", "dien_thoai": ""}], columns=IMPORT_COLS)
    return xlsx_response({
        "tai_khoan": sample,
        "vai_tro": pd.DataFrame([{"ma_vai_tro": r.code, "ten": r.name, "cap": LEVEL_NAMES.get(r.level)} for r in roles]),
        "don_vi": pd.DataFrame([{"ma_don_vi": u.code, "ten": u.name, "dia_ban": u.region.name} for u in units]),
    }, "mau_nhap_tai_khoan.xlsx")


@router.post("/users/import")
async def import_users(request: Request, file: UploadFile = File(...), dry_run: bool = True,
                       db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    """dry_run=True: chỉ kiểm tra; False: tạo tài khoản, sinh mật khẩu tạm (bắt đổi khi đăng nhập lần đầu)."""
    from .admin import UserIn, _validate
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), dtype=str) if file.filename.lower().endswith(("xlsx", "xls")) \
            else pd.read_csv(io.StringIO(content.decode("utf-8-sig")), dtype=str)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Không đọc được tệp: {e}")
    df = df.fillna("")
    missing = [c for c in IMPORT_COLS[:4] if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Thiếu cột: {', '.join(missing)}")
    roles = {r.code: r for r in db.scalars(select(Role))}
    units = {u.code.upper(): u for u in db.scalars(select(Unit))}
    existing = set(db.scalars(select(User.username)))
    seen, results, created = set(), [], 0
    for i, row in enumerate(df.to_dict(orient="records"), start=2):
        un = str(row["ten_dang_nhap"]).strip().lower()
        res = {"row": i, "username": un, "full_name": row["ho_ten"], "ok": False, "message": "", "password": None}
        try:
            if not un or not row["ho_ten"].strip():
                raise ValueError("Thiếu tên đăng nhập hoặc họ tên")
            if un in existing or un in seen:
                raise ValueError("Tên đăng nhập đã tồn tại")
            role = roles.get(str(row["ma_vai_tro"]).strip())
            unit = units.get(str(row["ma_don_vi"]).strip().upper())
            if not role:
                raise ValueError("Mã vai trò không tồn tại")
            if row["ma_don_vi"] and not unit:
                raise ValueError("Mã đơn vị không tồn tại")
            body = UserIn(username=un, full_name=row["ho_ten"].strip(), role_id=role.id, unit_id=unit.id if unit else None,
                          position=row.get("chuc_vu") or None, email=row.get("email") or None, phone=row.get("dien_thoai") or None)
            data = _validate(db, me, body)
            seen.add(un)
            res["ok"], res["message"] = True, f"{role.name} – {unit.name if unit else ''}"
            if not dry_run:
                pw = "Tn" + secrets.token_hex(3) + "!"
                data["username"] = un
                db.add(User(**data, password_hash=hash_password(pw), must_change_password=True))
                res["password"] = pw
                created += 1
        except HTTPException as e:
            res["message"] = e.detail
        except ValueError as e:
            res["message"] = str(e)
        results.append(res)
    if not dry_run:
        audit(db, me, "import_users", "user", None, {"file": file.filename, "created": created}, request)
        db.commit()
    return {"dry_run": dry_run, "total": len(results), "valid": sum(r["ok"] for r in results), "created": created, "rows": results}


@router.get("/users/export.xlsx")
def export_users(request: Request, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    stmt = select(User)
    ids = managed_unit_ids(db, me)
    if ids is not None:
        stmt = stmt.where(User.unit_id.in_(ids or [-1]))
    rows = [admin_user_out(u) for u in db.scalars(stmt.order_by(User.id)).unique()]
    df = pd.DataFrame([{"Tên đăng nhập": r["username"], "Họ tên": r["full_name"], "Cấp": r["level_name"], "Vai trò": r["role"]["name"],
                        "Đơn vị": (r["unit"] or {}).get("name"), "Chức vụ": r["position"], "Email": r["email"],
                        "Trạng thái": "Hoạt động" if r["is_active"] else "Đã khóa",
                        "Đăng nhập gần nhất": r["last_login"].strftime("%d/%m/%Y %H:%M") if r["last_login"] else "Chưa đăng nhập"}
                       for r in rows])
    audit(db, me, "export_users", "user", None, {"rows": len(df)}, request)
    db.commit()
    return xlsx_response({"tai_khoan": df}, f"danh_sach_tai_khoan_{date.today():%Y%m%d}.xlsx")


@router.get("/users/inactive")
def inactive_users(days: int | None = None, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    days = days or int(get_setting(db, "inactive_days"))
    cutoff = datetime.now() - timedelta(days=days)
    stmt = select(User).where(User.is_active, or_(User.last_login.is_(None), User.last_login < cutoff), User.id != me.id)
    ids = managed_unit_ids(db, me)
    if ids is not None:
        stmt = stmt.where(User.unit_id.in_(ids or [-1]))
    return {"days": days, "items": [admin_user_out(u) for u in db.scalars(stmt.order_by(User.last_login.nulls_first())).unique()]}


class IdsIn(BaseModel):
    ids: list[int]


@router.post("/users/bulk-lock")
def bulk_lock(body: IdsIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    n = 0
    for uid in body.ids:
        u = db.get(User, uid)
        if not u or u.id == me.id:
            continue
        ensure_manageable(db, me, u)
        u.is_active = False
        db.execute(update(UserSession).where(UserSession.user_id == uid, ~UserSession.revoked).values(revoked=True, revoked_reason="Tài khoản bị khóa"))
        n += 1
    audit(db, me, "bulk_lock", "user", None, {"ids": body.ids, "locked": n}, request)
    db.commit()
    return {"locked": n}


# ===================================================================== 3. chuyển giao công việc


def _handover_items(db: Session, u: User):
    working = ["dang_xu_ly", "tra_lai", "cho_duyet"]
    tasks = db.scalars(select(TaskAssignment).where(TaskAssignment.unit_id == u.unit_id, TaskAssignment.handler_name == u.full_name,
                                                    TaskAssignment.status.in_(working))).all() if u.unit_id else []
    am_units = list(db.scalars(select(AMAssignment.unit_id).where(AMAssignment.user_id == u.id)))
    return tasks, am_units


@router.get("/users/{uid}/handover")
def handover_preview(uid: int, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    ensure_manageable(db, me, u)
    tasks, am_units = _handover_items(db, u)
    cands = db.scalars(select(User).where(User.is_active, User.id != u.id, User.role_id == u.role_id,
                                          User.unit_id == u.unit_id if u.role.data_scope != "assigned" else True)).unique().all()
    if not cands and u.unit_id:
        cands = db.scalars(select(User).where(User.is_active, User.id != u.id, User.unit_id == u.unit_id)).unique().all()
    if not is_super(me):  # chỉ gợi ý người nhận nằm trong phạm vi quản trị của mình (tránh bàn giao bị từ chối)
        ids, roles = managed_unit_ids(db, me), {r.id for r in assignable_roles(db, me)}
        cands = [c for c in cands if c.unit_id in ids and c.role_id in roles]
    return {"user": admin_user_out(u),
            "tasks": [{"assignment_id": a.id, "code": a.task.code, "title": a.task.title, "status": a.status,
                       "deadline": a.task.deadline} for a in tasks],
            "am_units": len(am_units),
            "candidates": [{"id": c.id, "username": c.username, "full_name": c.full_name, "role": c.role.name} for c in cands]}


class HandoverIn(BaseModel):
    to_user_id: int
    lock_account: bool = True
    note: str | None = None


@router.post("/users/{uid}/handover")
def handover(uid: int, body: HandoverIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    u, to = db.get(User, uid), db.get(User, body.to_user_id)
    if not u or not to:
        raise HTTPException(404)
    ensure_manageable(db, me, u)
    ensure_manageable(db, me, to)
    if not to.is_active:
        raise HTTPException(400, "Người nhận bàn giao đã bị khóa")
    if u.unit_id and to.unit_id != u.unit_id and u.role.data_scope != "assigned":
        raise HTTPException(400, "Người nhận phải cùng đơn vị")
    tasks, am_units = _handover_items(db, u)
    for a in tasks:
        a.handler_name = to.full_name
        db.add(TaskLog(task_id=a.task_id, assignment_id=a.id, user_id=me.id, action="phan_cong",
                       note=f"[{a.unit.name}] Bàn giao từ {u.full_name} sang {to.full_name}. {body.note or ''}".strip()))
        db.add(Notification(user_id=to.id, kind="phan_cong", title=f"Nhận bàn giao: {a.task.title}", task_id=a.task_id,
                            body=f"Từ {u.full_name}"))
    for unit_id in am_units:
        if not db.get(AMAssignment, (to.id, unit_id)):
            db.add(AMAssignment(user_id=to.id, unit_id=unit_id))
    db.query(AMAssignment).filter(AMAssignment.user_id == u.id).delete()
    if body.lock_account:
        u.is_active = False
        db.execute(update(UserSession).where(UserSession.user_id == u.id, ~UserSession.revoked).values(revoked=True, revoked_reason="Đã bàn giao, khóa tài khoản"))
    audit(db, me, "handover", "user", uid, {"to": to.username, "tasks": len(tasks), "am_units": len(am_units), "locked": body.lock_account}, request)
    db.commit()
    return {"tasks": len(tasks), "am_units": len(am_units), "locked": body.lock_account}


# ===================================================================== 4. cấu hình hệ thống


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    return all_settings(db)


@router.put("/settings")
def put_settings(values: dict, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    try:
        for k, v in values.items():
            set_setting(db, k, v, me.username)
    except KeyError as e:
        raise HTTPException(400, f"Tham số không tồn tại: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit(db, me, "update_settings", "settings", None, values, request)
    db.commit()
    return all_settings(db)


@router.get("/periods")
def admin_periods(db: Session = Depends(get_db), me: User = Depends(require("role.manage", "catalog.manage"))):
    from ..models import DTIScore, UnitMetric
    counts = dict(db.execute(select(UnitMetric.period_id, func.count()).group_by(UnitMetric.period_id)).all())
    scored = dict(db.execute(select(DTIScore.period_id, func.count()).group_by(DTIScore.period_id)).all())
    return [{"id": p.id, "code": p.code, "name": p.name, "start_date": p.start_date, "end_date": p.end_date,
             "is_current": p.is_current, "is_locked": p.is_locked, "metric_count": counts.get(p.id, 0), "unit_count": scored.get(p.id, 0)}
            for p in db.scalars(select(Period).order_by(Period.start_date.desc()))]


@router.post("/periods")
def create_next_period(request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    last = db.scalar(select(Period).order_by(Period.start_date.desc()))
    y, q = (last.year, last.quarter + 1) if last.quarter < 4 else (last.year + 1, 1)
    sd = date(y, 3 * q - 2, 1)
    ed = date(y + (q == 4), (3 * q) % 12 + 1, 1) - timedelta(days=1)
    p = Period(code=f"{y}-Q{q}", name=f"Quý {q}/{y}", year=y, quarter=q, start_date=sd, end_date=ed)
    db.add(p)
    audit(db, me, "create_period", "period", p.code, request=request)
    db.commit()
    return {"code": p.code}


class PeriodIn(BaseModel):
    is_current: bool | None = None
    is_locked: bool | None = None


@router.put("/periods/{pid}")
def update_period(pid: int, body: PeriodIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    p = db.get(Period, pid)
    if not p:
        raise HTTPException(404)
    if body.is_current:
        db.execute(update(Period).values(is_current=False))
        p.is_current = True
    if body.is_locked is not None:
        if body.is_locked and p.is_current:
            raise HTTPException(400, "Không khóa kỳ hiện hành – hãy chuyển kỳ hiện hành trước")
        p.is_locked = body.is_locked
    audit(db, me, "update_period", "period", p.code, body.model_dump(), request)
    db.commit()
    return {"ok": True}


@router.get("/regions")
def admin_regions(db: Session = Depends(get_db), me: User = Depends(require("catalog.manage"))):
    counts = dict(db.execute(select(Unit.region_id, func.count()).group_by(Unit.region_id)).all())
    return [{"id": r.id, "code": r.code, "name": r.name, "type": r.type, "population": r.population, "area_km2": r.area_km2,
             "unit_count": counts.get(r.id, 0)} for r in db.scalars(select(Region).order_by(Region.type.desc(), Region.name))]


class RegionIn(BaseModel):
    code: str
    name: str
    type: str
    population: int | None = None
    area_km2: float | None = None


@router.post("/regions")
def create_region(body: RegionIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("catalog.manage"))):
    if body.type not in ("phuong", "xa", "dac_khu"):
        raise HTTPException(400, "Loại địa bàn: phường, xã hoặc đặc khu")
    if db.scalar(select(Region).where(Region.code == body.code)):
        raise HTTPException(400, "Mã địa bàn đã tồn tại")
    tinh = db.scalar(select(Region).where(Region.type == "tinh"))
    r = Region(**body.model_dump(), parent_id=tinh.id if tinh else None)
    db.add(r)
    audit(db, me, "create", "region", body.code, body.model_dump(), request)
    db.commit()
    return {"id": r.id}


@router.put("/regions/{rid}")
def update_region(rid: int, body: RegionIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("catalog.manage"))):
    r = db.get(Region, rid)
    if not r:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude={"code"}).items():
        setattr(r, k, v)
    audit(db, me, "update", "region", r.code, body.model_dump(), request)
    db.commit()
    return {"ok": True}


# ===================================================================== 5. thông báo hệ thống


class AnnounceIn(BaseModel):
    title: str
    body: str | None = None
    target: str = "all"
    severity: str = "info"


@router.get("/announcements")
def list_announcements(db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    return [{"id": a.id, "title": a.title, "body": a.body, "target": a.target, "target_name": "Tất cả" if a.target == "all" else LEVEL_NAMES.get(a.target),
             "severity": a.severity, "recipients": a.recipients, "created_by": a.created_by, "created_at": a.created_at}
            for a in db.scalars(select(Announcement).order_by(Announcement.id.desc()).limit(50))]


@router.post("/announcements")
def announce(body: AnnounceIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    if body.target != "all" and body.target not in LEVEL_NAMES:
        raise HTTPException(400, "Đối tượng nhận không hợp lệ")
    stmt = select(User.id).join(Role, Role.id == User.role_id).where(User.is_active)
    if body.target != "all":
        stmt = stmt.where(Role.level == body.target)
    ids = list(db.scalars(stmt))
    prefix = {"warning": "⚠ ", "critical": "‼ "}.get(body.severity, "")
    for uid in ids:
        db.add(Notification(user_id=uid, kind="he_thong", title=prefix + body.title, body=body.body))
    a = Announcement(**body.model_dump(), recipients=len(ids), created_by=me.username)
    db.add(a)
    audit(db, me, "announce", "announcement", None, {"title": body.title, "target": body.target, "recipients": len(ids)}, request)
    db.commit()
    return {"recipients": len(ids)}


# ===================================================================== 6. giám sát & sao lưu


@router.get("/monitor")
def monitor(db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    db_size = db.scalar(text("SELECT pg_database_size(current_database())"))
    tables = db.execute(text("""SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables
                                ORDER BY schemaname, n_live_tup DESC""")).all()
    by_schema: dict[str, int] = {}
    for sch, _, n in tables:
        by_schema[sch] = by_schema.get(sch, 0) + int(n)
    since = datetime.now() - timedelta(hours=24)
    errors = db.scalars(select(ApiError).order_by(ApiError.id.desc()).limit(20)).all()
    up = os.path.join(Path(__file__).resolve().parents[2], settings.upload_dir)
    upload_size = sum(f.stat().st_size for f in Path(up).glob("*") if f.is_file()) if os.path.isdir(up) else 0
    return {
        "uptime_seconds": int(time.time() - STARTED),
        "db_version": db.scalar(text("SHOW server_version")), "db_size": db_size,
        "schemas": [{"schema": k, "rows": v} for k, v in by_schema.items()],
        "top_tables": [{"schema": s, "table": t, "rows": int(n)} for s, t, n in tables[:12]],
        "active_sessions": db.scalar(select(func.count(UserSession.id)).where(~UserSession.revoked, UserSession.expires_at > datetime.now(),
                                                                               UserSession.last_seen > datetime.now() - timedelta(minutes=30))),
        "errors_24h": db.scalar(select(func.count(ApiError.id)).where(ApiError.created_at >= since)),
        "recent_errors": [{"method": e.method, "path": e.path, "status": e.status, "message": e.message, "created_at": e.created_at} for e in errors],
        "upload_size": upload_size,
        "backup_count": db.scalar(select(func.count(BackupRecord.id))),
        "last_backup": db.scalar(select(func.max(BackupRecord.created_at)).where(BackupRecord.status == "thanh_cong")),
    }


def _pg_dump() -> str | None:
    found = shutil.which("pg_dump")
    if found:
        return found
    for v in ("17", "16", "15"):
        p = Path(f"C:/Program Files/PostgreSQL/{v}/bin/pg_dump.exe")
        if p.exists():
            return str(p)
    return None


@router.get("/backups")
def list_backups(db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    return [{"id": b.id, "file_name": b.file_name, "size": b.size, "status": b.status, "message": b.message,
             "created_by": b.created_by, "created_at": b.created_at, "exists": (BACKUP_DIR / b.file_name).exists()}
            for b in db.scalars(select(BackupRecord).order_by(BackupRecord.id.desc()))]


@router.post("/backups")
def create_backup(request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    exe = _pg_dump()
    name = f"dti_{datetime.now():%Y%m%d_%H%M%S}.dump"
    rec = BackupRecord(file_name=name, created_by=me.username, status="loi")
    if not exe:
        rec.message = "Không tìm thấy pg_dump trên máy chủ"
    else:
        url = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql"))
        env = {**os.environ, "PGPASSWORD": url.password or ""}
        cmd = [exe, "-h", url.hostname or "localhost", "-p", str(url.port or 5432), "-U", url.username or "postgres",
               "-F", "c", "-f", str(BACKUP_DIR / name), url.path.lstrip("/")]
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                rec.status, rec.size = "thanh_cong", (BACKUP_DIR / name).stat().st_size
                rec.message = "Sao lưu định dạng custom (pg_restore để phục hồi)"
            else:
                rec.message = (r.stderr or "pg_dump lỗi")[:500]
        except Exception as e:  # noqa: BLE001
            rec.message = str(e)[:500]
    db.add(rec)
    audit(db, me, "backup", "backup", name, {"status": rec.status}, request)
    db.commit()
    if rec.status != "thanh_cong":
        raise HTTPException(500, f"Sao lưu thất bại: {rec.message}")
    return {"file_name": name, "size": rec.size}


@router.get("/backups/{bid}/download")
def download_backup(bid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    b = db.get(BackupRecord, bid)
    if not b or not (BACKUP_DIR / b.file_name).exists():
        raise HTTPException(404)
    audit(db, me, "download_backup", "backup", b.file_name, request=request)
    db.commit()
    return FileResponse(BACKUP_DIR / b.file_name, filename=b.file_name)


@router.delete("/backups/{bid}")
def delete_backup(bid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    b = db.get(BackupRecord, bid)
    if not b:
        raise HTTPException(404)
    (BACKUP_DIR / b.file_name).unlink(missing_ok=True)
    db.delete(b)
    audit(db, me, "delete_backup", "backup", b.file_name, request=request)
    db.commit()
    return {"ok": True}


# ===================================================================== 7. nhật ký nâng cao & cảnh báo bảo mật


def _audit_query(db, me, action, username, date_from, date_to, entity):
    stmt = select(AuditLog)
    ids = managed_unit_ids(db, me)
    if ids is not None:
        stmt = stmt.where(AuditLog.username.in_(select(User.username).where(User.unit_id.in_(ids or [-1]))))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if username:
        stmt = stmt.where(AuditLog.username.ilike(f"%{username}%"))
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at < date_to + timedelta(days=1))
    return stmt


@router.get("/audit")
def audit_search(page: int = 1, size: int = 30, action: str | None = None, username: str | None = None, entity: str | None = None,
                 date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
                 me: User = Depends(require("audit.view"))):
    stmt = _audit_query(db, me, action, username, date_from, date_to, entity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)).all()
    actions = list(db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)))
    return {"total": total, "actions": actions, "items": [
        {"id": a.id, "username": a.username, "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
         "detail": a.detail, "ip": a.ip, "created_at": a.created_at} for a in rows]}


@router.get("/audit/export.xlsx")
def audit_export(request: Request, action: str | None = None, username: str | None = None, entity: str | None = None,
                 date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db),
                 me: User = Depends(require("audit.view"))):
    rows = db.scalars(_audit_query(db, me, action, username, date_from, date_to, entity).order_by(AuditLog.id.desc()).limit(20000)).all()
    df = pd.DataFrame([{"Thời gian": a.created_at.strftime("%d/%m/%Y %H:%M:%S"), "Người dùng": a.username, "Hành động": a.action,
                        "Đối tượng": a.entity, "Mã": a.entity_id, "IP": a.ip, "Chi tiết": str(a.detail or "")[:500]} for a in rows])
    audit(db, me, "export_audit", "audit", None, {"rows": len(df)}, request)
    db.commit()
    return xlsx_response({"nhat_ky": df}, f"nhat_ky_{date.today():%Y%m%d}.xlsx")


@router.get("/security-alerts")
def security_alerts(db: Session = Depends(get_db), me: User = Depends(require("audit.view"))):
    """Phát hiện hành vi bất thường từ nhật ký (7 ngày gần nhất)."""
    since = datetime.now() - timedelta(days=7)
    alerts = []
    fails = db.execute(select(AuditLog.username, func.count(), func.max(AuditLog.created_at), func.array_agg(func.distinct(AuditLog.ip)))
                       .where(AuditLog.action == "login_failed", AuditLog.created_at >= since)
                       .group_by(AuditLog.username).having(func.count() >= 3)).all()
    for un, n, last, ips in fails:
        alerts.append({"type": "Đăng nhập sai nhiều lần", "severity": "cao" if n >= 5 else "trung_binh", "username": un,
                       "detail": f"{n} lần sai trong 7 ngày, IP: {', '.join(i for i in ips if i)}", "at": last})
    for u in db.scalars(select(User).where(User.locked_until > datetime.now())):
        alerts.append({"type": "Tài khoản đang bị khóa tạm", "severity": "trung_binh", "username": u.username,
                       "detail": f"Đến {u.locked_until:%H:%M %d/%m}", "at": u.locked_until})
    h1, h2 = int(get_setting(db, "work_hour_start")), int(get_setting(db, "work_hour_end"))
    off = db.scalars(select(AuditLog).where(AuditLog.action == "login", AuditLog.created_at >= since,
                                           or_(func.extract("hour", AuditLog.created_at) < h1,
                                               func.extract("hour", AuditLog.created_at) >= h2))
                     .order_by(AuditLog.id.desc()).limit(30)).all()
    for a in off:
        alerts.append({"type": "Đăng nhập ngoài giờ làm việc", "severity": "thap", "username": a.username,
                       "detail": f"Lúc {a.created_at:%H:%M %d/%m} từ IP {a.ip}", "at": a.created_at})
    for a in db.scalars(select(AuditLog).where(AuditLog.created_at >= since, AuditLog.action.in_(
            ["impersonate_start", "update_settings", "backup", "download_backup", "create"])).order_by(AuditLog.id.desc()).limit(40)):
        if a.action == "create" and a.entity != "role":
            continue
        name = {"impersonate_start": "Xem dưới vai trò người dùng khác", "update_settings": "Thay đổi cấu hình hệ thống",
                "backup": "Sao lưu cơ sở dữ liệu", "download_backup": "Tải bản sao lưu CSDL", "create": "Tạo vai trò mới"}[a.action]
        alerts.append({"type": name, "severity": "thap" if a.action != "download_backup" else "trung_binh", "username": a.username,
                       "detail": str(a.detail or "")[:160], "at": a.created_at})
    order = {"cao": 0, "trung_binh": 1, "thap": 2}
    alerts.sort(key=lambda x: (order[x["severity"]], -(x["at"].timestamp() if x["at"] else 0)))
    if not is_super(me):
        names = set(db.scalars(select(User.username).where(User.unit_id.in_(managed_unit_ids(db, me) or [-1]))))
        alerts = [a for a in alerts if a["username"] in names]
    return alerts


# ===================================================================== 8. khóa API tích hợp

API_SCOPES = {"dti.read": "Đọc kết quả DTI theo kỳ", "metrics.push": "Đẩy số liệu tiêu chí vào pipeline",
              "units.read": "Đọc danh mục đơn vị"}


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.get("/api-keys")
def list_keys(db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    return {"scopes": API_SCOPES, "items": [
        {"id": k.id, "name": k.name, "prefix": k.prefix, "scopes": k.scopes, "created_by": k.created_by, "created_at": k.created_at,
         "expires_at": k.expires_at, "last_used_at": k.last_used_at, "use_count": k.use_count, "revoked": k.revoked}
        for k in db.scalars(select(ApiKey).order_by(ApiKey.id.desc()))]}


class KeyIn(BaseModel):
    name: str
    scopes: list[str]
    expires_days: int | None = 365


@router.post("/api-keys")
def create_key(body: KeyIn, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    bad = [s for s in body.scopes if s not in API_SCOPES]
    if bad or not body.scopes:
        raise HTTPException(400, "Phạm vi quyền không hợp lệ")
    raw = "dti_" + secrets.token_urlsafe(32)
    k = ApiKey(name=body.name, prefix=raw[:12], key_hash=hash_key(raw), scopes=body.scopes, created_by=me.username,
               expires_at=datetime.now() + timedelta(days=body.expires_days) if body.expires_days else None)
    db.add(k)
    audit(db, me, "create_api_key", "api_key", k.prefix, {"name": body.name, "scopes": body.scopes}, request)
    db.commit()
    return {"id": k.id, "key": raw, "prefix": k.prefix}


@router.post("/api-keys/{kid}/revoke")
def revoke_key(kid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    need_super(me)
    k = db.get(ApiKey, kid)
    if not k:
        raise HTTPException(404)
    k.revoked = True
    audit(db, me, "revoke_api_key", "api_key", k.prefix, request=request)
    db.commit()
    return {"ok": True}


# ===================================================================== thiết lập tỉnh mới: nhập danh mục & trạng thái

CATEGORY_META = {  # mã phân loại: (tên, loại hình, cấp)
    "ubnd_tinh": ("UBND tỉnh/thành phố", "hanh_chinh", "tinh"), "van_phong": ("Văn phòng UBND tỉnh", "hanh_chinh", "tinh"),
    "so_nganh": ("Sở, ban, ngành", "hanh_chinh", "tinh"), "ubnd_xa": ("UBND xã, phường, đặc khu", "hanh_chinh", "xa"),
    "thpt": ("Trường THPT", "giao_duc", "tinh"), "thcs": ("Trường THCS", "giao_duc", "xa"),
    "tieu_hoc": ("Trường Tiểu học", "giao_duc", "xa"), "mam_non": ("Trường Mầm non", "giao_duc", "xa"),
}


def _num(v):
    s = str(v).strip()
    return int(float(s)) if s not in ("", "nan", "None") else None


@router.get("/catalog/template.xlsx")
def catalog_template(db: Session = Depends(get_db), me: User = Depends(require("catalog.manage"))):
    tinh = db.scalar(select(Region).where(Region.type == "tinh"))
    regions = pd.DataFrame([{"ma": "X001", "ten": "Phường Trung Tâm", "loai": "phuong", "dan_so": 50000, "dien_tich_km2": 20.5},
                            {"ma": "X002", "ten": "Xã Bình An", "loai": "xa", "dan_so": 30000, "dien_tich_km2": 85}])
    units = pd.DataFrame([
        {"ma_don_vi": "HC.T01", "ten_don_vi": "Ủy ban nhân dân tỉnh", "phan_loai": "ubnd_tinh", "ma_dia_ban": "", "ma_don_vi_cap_tren": "",
         "nguoi_dung_dau": "", "dien_thoai": "", "email": "", "so_cbccvc": 60, "so_hoc_sinh": ""},
        {"ma_don_vi": "HC.S01", "ten_don_vi": "Sở Khoa học và Công nghệ", "phan_loai": "so_nganh", "ma_dia_ban": "", "ma_don_vi_cap_tren": "HC.T01",
         "nguoi_dung_dau": "", "dien_thoai": "", "email": "", "so_cbccvc": 80, "so_hoc_sinh": ""},
        {"ma_don_vi": "HC.X001", "ten_don_vi": "UBND Phường Trung Tâm", "phan_loai": "ubnd_xa", "ma_dia_ban": "X001", "ma_don_vi_cap_tren": "",
         "nguoi_dung_dau": "", "dien_thoai": "", "email": "", "so_cbccvc": 45, "so_hoc_sinh": ""},
        {"ma_don_vi": "GD.X001.TH1", "ten_don_vi": "Trường Tiểu học Trung Tâm", "phan_loai": "tieu_hoc", "ma_dia_ban": "X001",
         "ma_don_vi_cap_tren": "HC.X001", "nguoi_dung_dau": "", "dien_thoai": "", "email": "", "so_cbccvc": 40, "so_hoc_sinh": 900},
    ])
    guide = pd.DataFrame([{"phan_loai": k, "ten": v[0], "loai_hinh": v[1], "cap": "Tỉnh" if v[2] == "tinh" else "Xã"}
                          for k, v in CATEGORY_META.items()])
    note = pd.DataFrame({"Hướng dẫn": [
        "Sheet dia_ban: loai = phuong | xa | dac_khu. Mã địa bàn là duy nhất.",
        "Sheet don_vi: đơn vị cấp tỉnh (UBND tỉnh, Văn phòng, Sở, THPT) có thể để trống ma_dia_ban → gắn với địa bàn cấp tỉnh"
        + (f" ({tinh.name})" if tinh else "") + ".",
        "UBND xã và trường MN/TH/THCS bắt buộc có ma_dia_ban.",
        "ma_don_vi_cap_tren: trường MN/TH/THCS → mã UBND xã; THPT → mã Sở GD&ĐT; Sở → mã UBND tỉnh.",
        "Nhập lại cùng mã sẽ CẬP NHẬT thông tin (không tạo trùng).",
    ]})
    return xlsx_response({"huong_dan": note, "dia_ban": regions, "don_vi": units, "phan_loai": guide}, "mau_danh_muc_tinh.xlsx")


@router.post("/catalog/import")
async def catalog_import(request: Request, file: UploadFile = File(...), dry_run: bool = True,
                         db: Session = Depends(get_db), me: User = Depends(require("catalog.manage"))):
    """Nhập danh mục địa bàn + đơn vị từ Excel (sheet dia_ban, don_vi). Trùng mã → cập nhật."""
    from ..models import UnitInfra
    try:
        sheets = pd.read_excel(io.BytesIO(await file.read()), sheet_name=None, dtype=str)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Không đọc được tệp Excel: {e}")
    tinh = db.scalar(select(Region).where(Region.type == "tinh"))
    if not tinh:
        raise HTTPException(400, "Chưa có địa bàn cấp tỉnh – hãy khởi tạo hệ thống cho tỉnh trước")
    regions = {r.code.upper(): r for r in db.scalars(select(Region))}
    units = {u.code.upper(): u for u in db.scalars(select(Unit))}
    rep = {"regions": {"new": 0, "update": 0, "errors": []}, "units": {"new": 0, "update": 0, "errors": []}}

    for i, row in enumerate(sheets.get("dia_ban", pd.DataFrame()).fillna("").to_dict(orient="records"), start=2):
        code, name, typ = str(row.get("ma", "")).strip().upper(), str(row.get("ten", "")).strip(), str(row.get("loai", "")).strip()
        if not code and not name:
            continue
        if not code or not name or typ not in ("phuong", "xa", "dac_khu"):
            rep["regions"]["errors"].append(f"dia_ban dòng {i}: thiếu mã/tên hoặc loại không hợp lệ ({typ})")
            continue
        try:
            pop = _num(row.get("dan_so", ""))
            area = float(row["dien_tich_km2"]) if str(row.get("dien_tich_km2", "")).strip() else None
        except ValueError:
            rep["regions"]["errors"].append(f"dia_ban dòng {i}: dân số/diện tích không phải số")
            continue
        r = regions.get(code)
        rep["regions"]["update" if r else "new"] += 1
        if not dry_run:
            r = r or Region(code=code, parent_id=tinh.id)
            r.name, r.type, r.population, r.area_km2 = name, typ, pop, area
            db.add(r)
            regions[code] = r
        elif not r:
            regions[code] = Region(code=code, name=name, type=typ)  # để kiểm tra đơn vị tham chiếu
    if not dry_run:
        db.flush()

    pending_parent = []
    for i, row in enumerate(sheets.get("don_vi", pd.DataFrame()).fillna("").to_dict(orient="records"), start=2):
        code, name, cat = str(row.get("ma_don_vi", "")).strip().upper(), str(row.get("ten_don_vi", "")).strip(), str(row.get("phan_loai", "")).strip()
        if not code and not name:
            continue
        meta = CATEGORY_META.get(cat)
        rcode = str(row.get("ma_dia_ban", "")).strip().upper()
        err = None
        if not code or not name:
            err = "thiếu mã hoặc tên"
        elif not meta:
            err = f"phân loại '{cat}' không hợp lệ"
        elif rcode and rcode not in regions:
            err = f"mã địa bàn '{rcode}' không có"
        elif not rcode and meta[2] == "xa":
            err = "UBND xã / trường MN-TH-THCS phải có mã địa bàn"
        if err:
            rep["units"]["errors"].append(f"don_vi dòng {i}: {err}")
            continue
        u = units.get(code)
        rep["units"]["update" if (u is not None and u.id) else "new"] += 1
        if dry_run:
            units.setdefault(code, Unit(code=code))
            if str(row.get("ma_don_vi_cap_tren", "")).strip() and str(row["ma_don_vi_cap_tren"]).strip().upper() not in units:
                pending_parent.append((None, str(row["ma_don_vi_cap_tren"]).strip().upper(), i))
            continue
        is_new = u is None
        u = u or Unit(code=code)
        u.name, u.category, u.unit_type, u.level = name, cat, meta[1], meta[2]
        u.region_id = regions[rcode].id if rcode else tinh.id
        u.head_name = row.get("nguoi_dung_dau") or u.head_name
        u.phone, u.email = row.get("dien_thoai") or u.phone, row.get("email") or u.email
        u.staff_count = _num(row.get("so_cbccvc", "")) or u.staff_count
        u.student_count = _num(row.get("so_hoc_sinh", "")) or u.student_count
        u.is_active = True
        db.add(u)
        db.flush()
        if is_new:
            db.add(UnitInfra(unit_id=u.id))
        units[code] = u
        if str(row.get("ma_don_vi_cap_tren", "")).strip():
            pending_parent.append((u, str(row["ma_don_vi_cap_tren"]).strip().upper(), i))
    for u, pcode, i in pending_parent:
        parent = units.get(pcode)
        if parent is None:
            rep["units"]["errors"].append(f"don_vi dòng {i}: mã đơn vị cấp trên '{pcode}' không có")
        elif u is not None and parent.id:
            u.parent_unit_id = parent.id
    if not dry_run:
        audit(db, me, "import_catalog", "catalog", None,
              {k: {kk: vv for kk, vv in v.items() if kk != "errors"} for k, v in rep.items()}, request)
        db.commit()
    return {"dry_run": dry_run, **rep}


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db), me: User = Depends(require("role.manage"))):
    """Tiến độ thiết lập hệ thống cho một tỉnh (trang 'Thiết lập tỉnh mới')."""
    need_super(me)
    from ..models import Criterion, IngestBatch, Pillar
    from ..services.sysconfig import province_label
    by_level = dict(db.execute(select(Role.level, func.count(User.id)).join(User, User.role_id == Role.id)
                               .where(User.is_active).group_by(Role.level)).all())
    n_reg = db.scalar(select(func.count(Region.id)).where(Region.type != "tinh"))
    n_xa = db.scalar(select(func.count(Unit.id)).where(Unit.category == "ubnd_xa"))
    n_unit = db.scalar(select(func.count(Unit.id)))
    n_school = db.scalar(select(func.count(Unit.id)).where(Unit.unit_type == "giao_duc"))
    cur = db.scalar(select(Period).where(Period.is_current))
    n_crit = db.scalar(select(func.count(Criterion.id)).where(Criterion.is_active))
    w = db.scalar(select(func.sum(Pillar.weight))) or 0
    batches = db.scalar(select(func.count(IngestBatch.id)).where(IngestBatch.source_type.in_(["upload_csv", "upload_xlsx", "api"])))
    me_changed = me.password_changed_at is not None and not me.must_change_password
    demo = bool(get_setting(db, "demo_mode"))
    steps = [
        {"key": "province", "title": "Thông tin tỉnh triển khai", "done": bool(get_setting(db, "province_name")),
         "detail": province_label(db) or "Chưa đặt tên tỉnh"},
        {"key": "catalog", "title": "Danh mục địa bàn & đơn vị", "done": n_reg > 0 and n_xa > 0,
         "detail": f"{n_reg} xã/phường · {n_unit} đơn vị ({n_xa} UBND xã, {n_school} trường)"},
        {"key": "period", "title": "Kỳ đánh giá", "done": cur is not None, "detail": f"Kỳ hiện hành: {cur.name}" if cur else "Chưa có kỳ hiện hành"},
        {"key": "criteria", "title": "Bộ tiêu chí DTI", "done": n_crit > 0 and abs(w - 100) < 0.01,
         "detail": f"{n_crit} tiêu chí đang dùng · tổng trọng số trụ cột {w:g}"},
        {"key": "accounts", "title": "Tài khoản cán bộ", "done": by_level.get("tinh", 0) + by_level.get("so", 0) > 0 and by_level.get("xa", 0) > 0,
         "detail": f"Tỉnh {by_level.get('tinh', 0)} · Sở {by_level.get('so', 0)} · Xã {by_level.get('xa', 0)} · Trường {by_level.get('truong', 0)}"},
        {"key": "security", "title": "Bảo mật trước khi vận hành", "done": not demo and me_changed,
         "detail": ("Đã tắt chế độ demo" if not demo else "Chế độ demo đang BẬT")
         + (" · mật khẩu admin đã đổi" if me_changed else " · admin chưa đổi mật khẩu mặc định")},
        {"key": "data", "title": "Dữ liệu đánh giá đầu tiên", "done": batches > 0,
         "detail": f"{batches} lô dữ liệu đã nhập (Sở KH&CN thực hiện)"},
    ]
    return {"province": province_label(db), "done": sum(s["done"] for s in steps), "total": len(steps), "steps": steps}
