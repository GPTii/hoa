from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserSession
from ..security import (
    audit, create_session_token, get_current_user, hash_password, password_expired, perms_of, require, verify_password,
)
from ..services.sysconfig import check_password_policy, get_setting

router = APIRouter(prefix="/api/auth", tags=["Xác thực"])


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePwIn(BaseModel):
    old_password: str
    new_password: str


def user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "full_name": u.full_name, "email": u.email, "phone": u.phone,
        "position": u.position, "is_active": u.is_active,
        "role": {"id": u.role.id, "code": u.role.code, "name": u.role.name, "data_scope": u.role.data_scope, "level": u.role.level},
        "unit": {"id": u.unit.id, "name": u.unit.name, "unit_type": u.unit.unit_type} if u.unit else None,
        "region": {"id": u.region.id, "name": u.region.name} if u.region else None,
        "last_login": u.last_login,
        "locked_until": u.locked_until, "failed_logins": u.failed_logins,
    }


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    uname = body.username.strip()
    user = db.scalar(select(User).where(User.username == uname))
    now = datetime.now()
    if user and user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(423, f"Tài khoản tạm khóa do đăng nhập sai nhiều lần, thử lại sau {mins} phút "
                                 "hoặc liên hệ quản trị để mở khóa")
    if not user or not verify_password(body.password, user.password_hash):
        detail = {"reason": "sai_mat_khau" if user else "khong_ton_tai"}
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            limit = int(get_setting(db, "max_failed_logins"))
            if limit and user.failed_logins >= limit:
                user.locked_until = now + timedelta(minutes=int(get_setting(db, "lockout_minutes")))
                detail["locked"] = True
            detail["failed"] = user.failed_logins
        audit(db, None, "login_failed", "user", user.id if user else None, detail, request, username=uname)
        db.commit()
        if user and detail.get("locked"):
            raise HTTPException(423, f"Sai mật khẩu {user.failed_logins} lần – tài khoản bị khóa tạm "
                                     f"{get_setting(db, 'lockout_minutes')} phút")
        left = int(get_setting(db, "max_failed_logins")) - (user.failed_logins if user else 0)
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu" + (f" (còn {left} lần thử)" if user and left > 0 else ""))
    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa, liên hệ quản trị hệ thống")
    user.last_login, user.failed_logins, user.locked_until = now, 0, None
    token = create_session_token(db, user, request)
    audit(db, user, "login", request=request)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": user_out(user), "permissions": sorted(perms_of(user)),
            "must_change_password": user.must_change_password or password_expired(db, user)}


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(UserSession).where(UserSession.id == user.session_id).values(revoked=True, revoked_reason="Đăng xuất"))
    audit(db, user, "logout", request=request)
    db.commit()
    return {"ok": True}


SCOPE_NAMES = {"all": "Toàn tỉnh", "giao_duc": "Toàn bộ cơ sở giáo dục trong tỉnh", "region": "Các đơn vị trên địa bàn xã/phường",
               "unit": "Chỉ đơn vị mình", "assigned": "Các đơn vị được phân công"}
LEVEL_NAMES = {"he_thong": "Quản trị hệ thống", "tinh": "Cấp tỉnh", "so": "Sở, ngành", "xa": "Cấp xã, phường",
               "truong": "Cơ sở giáo dục", "khac": "Đối tác / hỗ trợ"}


@router.get("/public-config")
def public_config(db: Session = Depends(get_db)):
    from ..services.sysconfig import province_label
    return {"org_name": get_setting(db, "org_name"), "demo_mode": bool(get_setting(db, "demo_mode")),
            "province_name": get_setting(db, "province_name"), "province_label": province_label(db),
            "system_name": get_setting(db, "system_name"), "system_subtitle": get_setting(db, "system_subtitle"),
            "password_min_length": get_setting(db, "password_min_length"),
            "password_require_complex": bool(get_setting(db, "password_require_complex"))}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Chỉ ở chế độ demo: tài khoản thử nghiệm (tên đăng nhập + chức danh), không lộ quyền/cấu hình."""
    from ..models import Role
    if not get_setting(db, "demo_mode"):
        return []
    seen, out = set(), []
    for u, r in db.execute(select(User, Role).join(Role, Role.id == User.role_id).where(User.is_active)
                           .order_by(Role.sort_order, User.id)).all():
        if r.id in seen:
            continue
        seen.add(r.id)
        out.append({"username": u.username, "role_name": r.name, "level": r.level, "level_name": LEVEL_NAMES.get(r.level, r.level)})
    return out


@router.get("/my-role")
def my_role(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Thông tin vai trò CỦA CHÍNH người dùng: việc phụ trách và phạm vi dữ liệu (không trả danh sách quyền)."""
    r = user.role
    return {"name": r.name, "description": r.description, "level_name": LEVEL_NAMES.get(r.level, r.level),
            "scope_name": SCOPE_NAMES.get(r.data_scope, r.data_scope),
            "scope_detail": (user.region.name if r.data_scope == "region" and user.region else
                             user.unit.name if r.data_scope == "unit" and user.unit else None),
            "duties": [d.strip() for d in (r.duties or "").split("|") if d.strip()]}


@router.get("/my-sessions")
def my_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id, ~UserSession.revoked,
                                                UserSession.expires_at > datetime.now(), UserSession.imp_by.is_(None))
                      .order_by(UserSession.last_seen.desc())).all()
    return [{"id": s.id, "ip": s.ip, "user_agent": s.user_agent, "created_at": s.created_at, "last_seen": s.last_seen,
             "current": s.id == user.session_id} for s in rows]


@router.post("/my-sessions/revoke-others")
def revoke_my_others(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.id != user.session_id, ~UserSession.revoked)
                   .values(revoked=True, revoked_reason="Người dùng đăng xuất các thiết bị khác")).rowcount
    audit(db, user, "revoke_sessions", "user", user.id, {"count": n}, request)
    db.commit()
    return {"revoked": n}


@router.get("/roles-guide")
def roles_guide(db: Session = Depends(get_db), _=Depends(require("role.manage"))):
    """Toàn bộ vai trò + ma trận quyền + tài khoản – THÔNG TIN HỆ THỐNG, chỉ quản trị cấp tỉnh xem."""
    from ..models import Permission, Role
    all_perms = db.scalars(select(Permission).order_by(Permission.module, Permission.id)).all()
    demo = {}
    for u in db.scalars(select(User).where(User.is_active).order_by(User.id)):
        demo.setdefault(u.role_id, []).append({"id": u.id, "username": u.username, "full_name": u.full_name, "position": u.position,
                                               "unit": u.unit.name if u.unit else None})
    out = []
    for r in db.scalars(select(Role).order_by(Role.sort_order, Role.id)):
        codes = {p.code for p in r.permissions}
        out.append({"code": r.code, "name": r.name, "description": r.description, "level": r.level,
                    "level_name": LEVEL_NAMES.get(r.level, r.level), "data_scope": r.data_scope,
                    "scope_name": SCOPE_NAMES.get(r.data_scope, r.data_scope),
                    "duties": [d.strip() for d in (r.duties or "").split("|") if d.strip()],
                    "can": [p.name for p in all_perms if p.code in codes],
                    "cannot": [p.name for p in all_perms if p.code not in codes],
                    "permissions": sorted(codes), "demo_users": demo.get(r.id, [])})
    return out


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    imp = None
    if getattr(user, "imp_by", None):
        a = db.get(User, user.imp_by)
        imp = {"id": a.id, "username": a.username, "full_name": a.full_name} if a else None
    return {"user": user_out(user), "permissions": sorted(perms_of(user)), "impersonated_by": imp,
            "must_change_password": not imp and (user.must_change_password or password_expired(db, user)),
            "password_expired": password_expired(db, user)}


def _is_super_admin(u: User) -> bool:
    return u.role.data_scope == "all" and {"role.manage", "user.manage"} <= perms_of(u)


@router.post("/impersonate/{uid}")
def impersonate(uid: int, request: Request, db: Session = Depends(get_db), me_: User = Depends(get_current_user)):
    """Quản trị hệ thống xem giao diện & chức năng dưới vai trò một tài khoản khác (phiên CHỈ XEM)."""
    if getattr(me_, "imp_by", None):
        raise HTTPException(400, "Đang ở chế độ xem thử – hãy trở về quản trị trước")
    if not _is_super_admin(me_):
        raise HTTPException(403, "Chỉ quản trị hệ thống cấp tỉnh được xem dưới vai trò người khác")
    target = db.get(User, uid)
    if not target or not target.is_active:
        raise HTTPException(404, "Tài khoản không tồn tại hoặc đã khóa")
    if target.id == me_.id:
        raise HTTPException(400, "Không thể xem dưới vai trò của chính mình")
    token = create_session_token(db, target, request, imp_by=me_.id)
    audit(db, me_, "impersonate_start", "user", target.id, {"target": target.username, "role": target.role.code}, request)
    db.commit()
    return {"access_token": token, "user": user_out(target), "permissions": sorted(perms_of(target)),
            "impersonated_by": {"id": me_.id, "username": me_.username, "full_name": me_.full_name}}


@router.post("/stop-impersonate")
def stop_impersonate(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not getattr(user, "imp_by", None):
        raise HTTPException(400, "Không ở chế độ xem thử")
    admin = db.get(User, user.imp_by)
    if not admin or not admin.is_active or not _is_super_admin(admin):
        raise HTTPException(401, "Phiên quản trị không còn hợp lệ, vui lòng đăng nhập lại")
    db.execute(update(UserSession).where(UserSession.id == user.session_id).values(revoked=True, revoked_reason="Kết thúc xem thử"))
    token = create_session_token(db, admin, request)
    audit(db, admin, "impersonate_stop", "user", user.id, {"target": user.username}, request)
    db.commit()
    return {"access_token": token, "user": user_out(admin), "permissions": sorted(perms_of(admin))}


@router.post("/change-password")
def change_password(body: ChangePwIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if getattr(user, "imp_by", None):
        raise HTTPException(403, "Không đổi mật khẩu khi đang xem thử")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    if body.new_password == body.old_password:
        raise HTTPException(400, "Mật khẩu mới phải khác mật khẩu hiện tại")
    err = check_password_policy(db, body.new_password)
    if err:
        raise HTTPException(400, err)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password, user.password_changed_at = False, datetime.now()
    # đổi mật khẩu → đăng xuất mọi thiết bị khác
    db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.id != user.session_id, ~UserSession.revoked)
               .values(revoked=True, revoked_reason="Đã đổi mật khẩu"))
    audit(db, user, "change_password", "user", user.id, request=request)
    db.commit()
    return {"ok": True}
