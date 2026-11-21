"""Quản trị hệ thống – PHÂN CẤP QUẢN TRỊ.

- Quản trị hệ thống (cấp tỉnh, phạm vi toàn tỉnh): quản lý mọi tài khoản, tạo/sửa vai trò, ma trận quyền, nhật ký.
- Quản trị cấp xã/phường: chỉ quản lý tài khoản thuộc các đơn vị trên địa bàn (UBND xã + các trường) và
  chỉ gán được các vai trò cấp xã / cơ sở giáo dục (không tạo được quản trị khác, không gán vai trò cấp tỉnh).
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AMAssignment, AuditLog, Permission, Role, Unit, User
from ..security import audit, hash_password, perms_of, require, scoped_unit_ids
from .auth import LEVEL_NAMES, SCOPE_NAMES, user_out

router = APIRouter(prefix="/api/admin", tags=["Quản trị hệ thống"])

# Quản trị cấp nào được gán vai trò thuộc cấp nào
ASSIGNABLE_LEVELS = {"xa": {"xa", "truong"}, "truong": {"truong"}, "so": {"so", "truong"}}
ADMIN_PERMS = {"user.manage", "role.manage"}


def is_super(me: User) -> bool:
    return me.role.data_scope == "all" and "user.manage" in perms_of(me)


def assignable_roles(db: Session, me: User) -> list[Role]:
    roles = db.scalars(select(Role).order_by(Role.sort_order, Role.id)).all()
    if is_super(me):
        return list(roles)
    levels = ASSIGNABLE_LEVELS.get(me.role.level, set())
    return [r for r in roles if r.level in levels and not ({p.code for p in r.permissions} & ADMIN_PERMS)]


def managed_unit_ids(db: Session, me: User) -> list[int] | None:
    return None if is_super(me) else (scoped_unit_ids(db, me) or [])


def ensure_manageable(db: Session, me: User, u: User):
    """Người bị thao tác phải thuộc phạm vi và có vai trò mà người quản trị được phép gán."""
    if is_super(me):
        return
    ids = managed_unit_ids(db, me)
    if u.unit_id not in ids or u.role_id not in {r.id for r in assignable_roles(db, me)}:
        raise HTTPException(403, "Tài khoản này nằm ngoài phạm vi quản trị của bạn")


def admin_user_out(u: User) -> dict:
    d = user_out(u)
    d["role"]["level"] = u.role.level
    d["level_name"] = LEVEL_NAMES.get(u.role.level, u.role.level)
    d["unit_region"] = u.unit.region.name if u.unit and u.unit.region else None
    d["created_at"] = u.created_at
    return d


class UserIn(BaseModel):
    username: str
    full_name: str
    password: str | None = None
    email: str | None = None
    phone: str | None = None
    position: str | None = None
    role_id: int
    unit_id: int | None = None
    is_active: bool = True


def _validate(db: Session, me: User, body: UserIn) -> dict:
    role = db.get(Role, body.role_id)
    if not role:
        raise HTTPException(400, "Vai trò không tồn tại")
    if role.id not in {r.id for r in assignable_roles(db, me)}:
        raise HTTPException(403, f"Bạn không được gán vai trò '{role.name}' (ngoài cấp quản trị của bạn)")
    unit = db.get(Unit, body.unit_id) if body.unit_id else None
    if role.data_scope != "all" and role.data_scope != "assigned" and not unit:
        raise HTTPException(400, "Vai trò này cần chọn đơn vị công tác")
    ids = managed_unit_ids(db, me)
    if ids is not None and (not unit or unit.id not in ids):
        raise HTTPException(403, "Chỉ tạo tài khoản cho đơn vị thuộc địa bàn bạn quản lý")
    # kiểm tra vai trò phù hợp loại đơn vị
    if unit and role.level == "truong" and unit.unit_type != "giao_duc":
        raise HTTPException(400, "Vai trò cấp trường chỉ gán cho người thuộc cơ sở giáo dục")
    if unit and role.level == "xa" and unit.category != "ubnd_xa":
        raise HTTPException(400, "Vai trò cấp xã chỉ gán cho người thuộc UBND xã/phường")
    data = body.model_dump(exclude={"password"})
    data["region_id"] = unit.region_id if unit else None  # phạm vi địa bàn suy ra từ đơn vị
    return data


@router.get("/users")
def list_users(q: str | None = None, role_id: int | None = None, level: str | None = None, unit_id: int | None = None,
               active: bool | None = None, page: int = 1, size: int = 20,
               db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    stmt = select(User).join(Role, Role.id == User.role_id)
    ids = managed_unit_ids(db, me)
    if ids is not None:
        stmt = stmt.where(User.unit_id.in_(ids or [-1]))
    if q:
        stmt = stmt.where(or_(User.username.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    if role_id:
        stmt = stmt.where(User.role_id == role_id)
    if level:
        stmt = stmt.where(Role.level == level)
    if unit_id:
        stmt = stmt.where(User.unit_id == unit_id)
    if active is not None:
        stmt = stmt.where(User.is_active == active)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Role.sort_order, User.id).offset((page - 1) * size).limit(size)).unique().all()
    manageable = {r.id for r in assignable_roles(db, me)}
    return {"total": total, "items": [{**admin_user_out(u), "manageable": is_super(me) or u.role_id in manageable} for u in items]}


@router.get("/context")
def admin_context(db: Session = Depends(get_db), me: User = Depends(require("user.manage"))):
    """Bối cảnh quản trị của người đang đăng nhập: phạm vi, vai trò được gán, đơn vị được chọn."""
    ids = managed_unit_ids(db, me)
    stmt = select(Unit).where(Unit.is_active)
    if ids is not None:
        stmt = stmt.where(Unit.id.in_(ids or [-1]))
    units = db.scalars(stmt.order_by(Unit.level, Unit.name)).all()
    return {
        "is_super": is_super(me), "level": me.role.level, "scope": "Toàn tỉnh" if ids is None else (me.region.name if me.region else "Đơn vị"),
        "roles": [{"id": r.id, "code": r.code, "name": r.name, "level": r.level, "level_name": LEVEL_NAMES.get(r.level, r.level),
                   "data_scope": r.data_scope, "scope_name": SCOPE_NAMES.get(r.data_scope)} for r in assignable_roles(db, me)],
        "units": [{"id": u.id, "name": u.name, "category": u.category, "unit_type": u.unit_type, "level": u.level,
                   "region": u.region.name} for u in units],
        "levels": [{"value": k, "label": v} for k, v in LEVEL_NAMES.items()],
    }


@router.post("/users")
def create_user(body: UserIn, request: Request, db: Session = Depends(get_db), me=Depends(require("user.manage"))):
    if db.scalar(select(User).where(User.username == body.username.strip())):
        raise HTTPException(400, "Tên đăng nhập đã tồn tại")
    from ..services.sysconfig import check_password_policy, get_setting
    err = check_password_policy(db, body.password or "")
    if err:
        raise HTTPException(400, err)
    data = _validate(db, me, body)
    data["username"] = body.username.strip()
    u = User(**data, password_hash=hash_password(body.password),
             must_change_password=bool(get_setting(db, "force_change_on_reset")))
    db.add(u)
    db.flush()
    audit(db, me, "create", "user", u.id, {"username": u.username, "role": u.role_id, "unit": u.unit_id}, request)
    db.commit()
    db.refresh(u)
    return admin_user_out(u)


@router.put("/users/{uid}")
def update_user(uid: int, body: UserIn, request: Request, db: Session = Depends(get_db), me=Depends(require("user.manage"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Không tìm thấy người dùng")
    ensure_manageable(db, me, u)
    if u.id == me.id and body.role_id != u.role_id:
        raise HTTPException(400, "Không thể tự đổi vai trò của chính mình")
    data = _validate(db, me, body) if u.id != me.id else {k: v for k, v in body.model_dump(exclude={"password"}).items()}
    for k, v in data.items():
        if k != "username":
            setattr(u, k, v)
    if body.password:
        from ..services.sysconfig import check_password_policy, get_setting
        err = check_password_policy(db, body.password)
        if err:
            raise HTTPException(400, err)
        u.password_hash = hash_password(body.password)
        u.must_change_password = u.id != me.id and bool(get_setting(db, "force_change_on_reset"))
    audit(db, me, "update", "user", uid, body.model_dump(exclude={"password"}), request)
    db.commit()
    db.refresh(u)
    return admin_user_out(u)


@router.delete("/users/{uid}")
def lock_user(uid: int, request: Request, db: Session = Depends(get_db), me=Depends(require("user.manage"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    if u.id == me.id:
        raise HTTPException(400, "Không thể tự khóa tài khoản của mình")
    ensure_manageable(db, me, u)
    u.is_active = not u.is_active
    if not u.is_active:  # khóa tài khoản → thu hồi mọi phiên đang đăng nhập
        from sqlalchemy import update as sa_update
        from ..models import UserSession
        db.execute(sa_update(UserSession).where(UserSession.user_id == u.id, ~UserSession.revoked)
                   .values(revoked=True, revoked_reason="Tài khoản bị khóa"))
    audit(db, me, "lock" if not u.is_active else "unlock", "user", uid, request=request)
    db.commit()
    return {"is_active": u.is_active}


@router.post("/users/{uid}/reset-password")
def reset_password(uid: int, request: Request, db: Session = Depends(get_db), me=Depends(require("user.manage"))):
    """Cấp lại mật khẩu tạm (hiển thị 1 lần để quản trị gửi cho người dùng)."""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    ensure_manageable(db, me, u)
    from ..services.sysconfig import get_setting
    temp = "Tn" + secrets.token_hex(3) + "!"
    u.password_hash = hash_password(temp)
    u.must_change_password = bool(get_setting(db, "force_change_on_reset"))
    u.failed_logins, u.locked_until = 0, None
    audit(db, me, "reset_password", "user", uid, request=request)
    db.commit()
    return {"temporary_password": temp}


@router.get("/users/{uid}/am-units")
def am_units(uid: int, db: Session = Depends(get_db), me=Depends(require("user.manage"))):
    return list(db.scalars(select(AMAssignment.unit_id).where(AMAssignment.user_id == uid)))


@router.put("/users/{uid}/am-units")
def set_am_units(uid: int, unit_ids: list[int], request: Request, db: Session = Depends(get_db), me=Depends(require("user.manage"))):
    if not is_super(me):
        raise HTTPException(403, "Chỉ quản trị cấp tỉnh phân công AM")
    db.query(AMAssignment).filter(AMAssignment.user_id == uid).delete()
    for unit_id in unit_ids:
        db.add(AMAssignment(user_id=uid, unit_id=unit_id))
    audit(db, me, "assign_am", "user", uid, {"units": unit_ids}, request)
    db.commit()
    return {"ok": True, "count": len(unit_ids)}


# ---------------- vai trò & quyền (chỉ quản trị cấp tỉnh)


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), me=Depends(require("role.manage", "user.manage"))):
    counts = dict(db.execute(select(User.role_id, func.count()).group_by(User.role_id)).all())
    roles = db.scalars(select(Role).order_by(Role.sort_order, Role.id)).all() if is_super(me) else assignable_roles(db, me)
    return [{"id": r.id, "code": r.code, "name": r.name, "description": r.description, "data_scope": r.data_scope,
             "level": r.level, "level_name": LEVEL_NAMES.get(r.level, r.level), "duties": r.duties,
             "permissions": [p.code for p in r.permissions], "user_count": counts.get(r.id, 0)} for r in roles]


@router.get("/permissions")
def list_permissions(db: Session = Depends(get_db), _=Depends(require("role.manage"))):
    return [{"id": p.id, "code": p.code, "name": p.name, "module": p.module}
            for p in db.scalars(select(Permission).order_by(Permission.module, Permission.id))]


class RoleIn(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    level: str | None = None
    duties: str | None = None
    permissions: list[str]
    data_scope: str | None = None


@router.post("/roles")
def create_role(body: RoleIn, request: Request, db: Session = Depends(get_db), me=Depends(require("role.manage"))):
    if not body.code or not body.name:
        raise HTTPException(400, "Nhập mã và tên vai trò")
    if db.scalar(select(Role).where(Role.code == body.code)):
        raise HTTPException(400, "Mã vai trò đã tồn tại")
    if body.data_scope not in SCOPE_NAMES or body.level not in LEVEL_NAMES:
        raise HTTPException(400, "Cấp hoặc phạm vi dữ liệu không hợp lệ")
    r = Role(code=body.code, name=body.name, description=body.description, level=body.level, duties=body.duties,
             data_scope=body.data_scope, sort_order=db.scalar(select(func.max(Role.sort_order))) + 1,
             permissions=list(db.scalars(select(Permission).where(Permission.code.in_(body.permissions)))))
    db.add(r)
    db.flush()
    audit(db, me, "create", "role", r.id, body.model_dump(), request)
    db.commit()
    return {"id": r.id}


@router.put("/roles/{rid}")
def update_role(rid: int, body: RoleIn, request: Request, db: Session = Depends(get_db), me=Depends(require("role.manage"))):
    r = db.get(Role, rid)
    if not r:
        raise HTTPException(404)
    if r.code == "admin" and "role.manage" not in body.permissions:
        raise HTTPException(400, "Không thể gỡ quyền quản lý vai trò khỏi Quản trị hệ thống")
    r.permissions = list(db.scalars(select(Permission).where(Permission.code.in_(body.permissions))))
    if body.data_scope in SCOPE_NAMES:
        r.data_scope = body.data_scope
    for f in ("name", "description", "duties"):
        if getattr(body, f):
            setattr(r, f, getattr(body, f))
    if body.level in LEVEL_NAMES:
        r.level = body.level
    audit(db, me, "update", "role", rid, body.model_dump(), request)
    db.commit()
    return {"ok": True}


@router.delete("/roles/{rid}")
def delete_role(rid: int, request: Request, db: Session = Depends(get_db), me=Depends(require("role.manage"))):
    r = db.get(Role, rid)
    if not r:
        raise HTTPException(404)
    if db.scalar(select(func.count(User.id)).where(User.role_id == rid)):
        raise HTTPException(400, "Vai trò đang có người dùng, hãy chuyển họ sang vai trò khác trước")
    if r.code == "admin":
        raise HTTPException(400, "Không thể xóa vai trò Quản trị hệ thống")
    db.delete(r)
    audit(db, me, "delete", "role", rid, {"code": r.code}, request)
    db.commit()
    return {"ok": True}


# ---------------- nhật ký hệ thống (quản trị xã chỉ xem nhật ký của người trong địa bàn)


@router.get("/audit-logs")
def audit_logs(page: int = 1, size: int = 30, action: str | None = None, username: str | None = None,
               db: Session = Depends(get_db), me=Depends(require("audit.view"))):
    stmt = select(AuditLog)
    ids = managed_unit_ids(db, me)
    if ids is not None:
        names = select(User.username).where(User.unit_id.in_(ids or [-1]))
        stmt = stmt.where(AuditLog.username.in_(names))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if username:
        stmt = stmt.where(AuditLog.username.ilike(f"%{username}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "items": [{"id": a.id, "username": a.username, "action": a.action, "entity": a.entity,
                                       "entity_id": a.entity_id, "detail": a.detail, "ip": a.ip,
                                       "created_at": a.created_at} for a in rows]}


@router.get("/stats")
def system_stats(db: Session = Depends(get_db), me=Depends(require("user.manage", "audit.view"))):
    ids = managed_unit_ids(db, me)
    q = select(User).join(Role, Role.id == User.role_id)
    if ids is not None:
        q = q.where(User.unit_id.in_(ids or [-1]))
    users = db.scalars(q).unique().all()
    by_level: dict[str, int] = {}
    for u in users:
        by_level[LEVEL_NAMES.get(u.role.level, u.role.level)] = by_level.get(LEVEL_NAMES.get(u.role.level, u.role.level), 0) + 1
    names = [u.username for u in users]
    return {
        "users": len(users), "active_users": sum(u.is_active for u in users), "locked_users": sum(not u.is_active for u in users),
        "never_login": sum(u.last_login is None for u in users),
        "units": len(ids) if ids is not None else db.scalar(select(func.count(Unit.id))),
        "by_level": [{"level": k, "count": v} for k, v in by_level.items()],
        "logins_7d": db.scalar(select(func.count(AuditLog.id)).where(
            AuditLog.action == "login", AuditLog.username.in_(names or ["-"]),
            AuditLog.created_at >= func.now() - func.make_interval(0, 0, 0, 7))),
    }


# ---------------- danh mục đơn vị (thông tin hành chính – không có số liệu đánh giá)


@router.get("/units")
def admin_units(q: str | None = None, region_id: int | None = None, category: str | None = None, page: int = 1, size: int = 20,
                db: Session = Depends(get_db), me: User = Depends(require("catalog.manage", "user.manage"))):
    from .catalog import CATEGORY_NAMES
    stmt = select(Unit)
    ids = managed_unit_ids(db, me)
    if ids is not None:
        stmt = stmt.where(Unit.id.in_(ids or [-1]))
    if q:
        stmt = stmt.where(or_(Unit.name.ilike(f"%{q}%"), Unit.code.ilike(f"%{q}%")))
    if region_id:
        stmt = stmt.where(Unit.region_id == region_id)
    if category:
        stmt = stmt.where(Unit.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Unit.level, Unit.code).offset((page - 1) * size).limit(size)).all()
    counts = dict(db.execute(select(User.unit_id, func.count()).where(User.unit_id.in_([u.id for u in rows] or [-1]))
                             .group_by(User.unit_id)).all())
    return {"total": total, "items": [{
        "id": u.id, "code": u.code, "name": u.name, "unit_type": u.unit_type, "category": u.category,
        "category_name": CATEGORY_NAMES.get(u.category, u.category), "level": u.level, "region_id": u.region_id,
        "region_name": u.region.name, "parent_unit_id": u.parent_unit_id, "address": u.address, "head_name": u.head_name,
        "phone": u.phone, "email": u.email, "staff_count": u.staff_count, "student_count": u.student_count,
        "is_active": u.is_active, "user_count": counts.get(u.id, 0)} for u in rows]}
