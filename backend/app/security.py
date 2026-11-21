import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import AMAssignment, AuditLog, Unit, User, UserSession

bearer = HTTPBearer(auto_error=False)
# Khi phải đổi mật khẩu (tài khoản mới, mật khẩu tạm, hết hạn) chỉ được gọi các API này
PW_CHANGE_ALLOWED = {"/api/auth/me", "/api/auth/change-password", "/api/auth/logout", "/api/auth/stop-impersonate",
                     "/api/auth/my-role"}


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def create_session_token(db: Session, user: User, request: Request | None = None, imp_by: int | None = None) -> str:
    """Tạo phiên đăng nhập (lưu DB để có thể thu hồi) và JWT mang mã phiên (jti).
    imp_by: id quản trị viên 'xem dưới vai trò' (phiên chỉ xem, tối đa 2 giờ)."""
    from .services.sysconfig import get_setting
    minutes = 120 if imp_by else int(get_setting(db, "session_minutes"))
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    jti = uuid.uuid4().hex
    db.add(UserSession(jti=jti, user_id=user.id, imp_by=imp_by, expires_at=exp.replace(tzinfo=None),
                       ip=request.client.host if request and request.client else None,
                       user_agent=(request.headers.get("user-agent", "")[:300] if request else None)))
    payload = {"sub": str(user.id), "role": user.role.code, "jti": jti, "exp": exp}
    if imp_by:
        payload["imp_by"] = imp_by
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        return None


def password_expired(db: Session, user: User) -> bool:
    from .services.sysconfig import get_setting
    days = int(get_setting(db, "password_expiry_days"))
    if not days:
        return False
    changed = user.password_changed_at or user.created_at
    return changed is not None and changed < datetime.now() - timedelta(days=days)


def get_current_user(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    payload = decode_token(cred.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    sess = db.scalar(select(UserSession).where(UserSession.jti == payload.get("jti", "")))
    if not sess or sess.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Phiên đăng nhập đã bị thu hồi" + (f" ({sess.revoked_reason})" if sess and sess.revoked_reason else ""))
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tài khoản không tồn tại hoặc bị khóa")
    now = datetime.now()
    if (now - sess.last_seen).total_seconds() > 60:  # cập nhật hoạt động gần nhất (giới hạn ghi DB)
        sess.last_seen = now
        db.commit()
    user.imp_by = payload.get("imp_by")  # thuộc tính tạm (không lưu DB)
    user.session_id = sess.id
    if not user.imp_by and (user.must_change_password or password_expired(db, user)) and request.url.path not in PW_CHANGE_ALLOWED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn cần đổi mật khẩu trước khi sử dụng hệ thống")
    return user


def perms_of(user: User) -> set[str]:
    return {p.code for p in user.role.permissions}


def require(*codes: str):
    """RBAC: yêu cầu người dùng có ít nhất một trong các quyền được liệt kê."""

    def dep(user: User = Depends(get_current_user)) -> User:
        if not perms_of(user) & set(codes):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền thực hiện chức năng này")
        return user

    return dep


def scoped_unit_ids(db: Session, user: User) -> list[int] | None:
    """Phạm vi dữ liệu (row-level). Trả về None = không giới hạn (toàn tỉnh)."""
    scope = user.role.data_scope
    if scope == "all":
        return None
    if scope == "region":
        if user.region_id is None:
            return None
        return list(db.scalars(select(Unit.id).where(Unit.region_id == user.region_id)))
    if scope == "giao_duc":  # Sở GD&ĐT: toàn bộ cơ sở giáo dục trong tỉnh + đơn vị mình
        ids = list(db.scalars(select(Unit.id).where(Unit.unit_type == "giao_duc")))
        return ids + ([user.unit_id] if user.unit_id else [])
    if scope == "assigned":
        return list(db.scalars(select(AMAssignment.unit_id).where(AMAssignment.user_id == user.id)))
    return [user.unit_id] if user.unit_id else []


def ensure_unit_access(db: Session, user: User, unit_id: int):
    ids = scoped_unit_ids(db, user)
    if ids is not None and unit_id not in ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Đơn vị nằm ngoài phạm vi dữ liệu được phân quyền")


def audit(db: Session, user: User | None, action: str, entity: str | None = None, entity_id=None,
          detail: dict | None = None, request: Request | None = None, username: str | None = None):
    db.add(AuditLog(
        user_id=user.id if user else None, username=user.username if user else username, action=action,
        entity=entity, entity_id=str(entity_id) if entity_id is not None else None, detail=detail,
        ip=request.client.host if request and request.client else None,
    ))
