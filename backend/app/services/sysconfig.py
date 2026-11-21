"""Tham số hệ thống (bảng system_settings) – quản trị chỉnh trên giao diện, có giá trị mặc định."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SystemSetting

# key: (giá trị mặc định, nhóm, mô tả, kiểu)
DEFAULTS: dict[str, tuple] = {
    "province_type": ("Tỉnh", "tinh", "Loại đơn vị hành chính cấp tỉnh (Tỉnh / Thành phố)", "text"),
    "province_name": ("", "tinh", "Tên tỉnh/thành phố triển khai (VD: Tây Ninh)", "text"),
    "system_name": ("DTI Platform", "tinh", "Tên hệ thống hiển thị", "text"),
    "system_subtitle": ("Trí tuệ dữ liệu chuyển đổi số", "tinh", "Dòng mô tả dưới tên hệ thống", "text"),
    "org_name": ("Sở Khoa học và Công nghệ", "tinh", "Đơn vị chủ quản vận hành hệ thống", "text"),
    "demo_mode": (True, "chung", "Hiện tài khoản thử nghiệm ở trang đăng nhập (tắt khi triển khai thật)", "bool"),
    "session_minutes": (720, "phien", "Thời gian một phiên đăng nhập (phút)", "int"),
    "max_failed_logins": (5, "bao_mat", "Số lần đăng nhập sai liên tiếp trước khi khóa tạm", "int"),
    "lockout_minutes": (15, "bao_mat", "Thời gian khóa tạm sau khi sai quá số lần (phút)", "int"),
    "password_min_length": (6, "mat_khau", "Độ dài tối thiểu của mật khẩu", "int"),
    "password_require_complex": (False, "mat_khau", "Bắt buộc có chữ hoa, chữ thường, chữ số và ký tự đặc biệt", "bool"),
    "password_expiry_days": (0, "mat_khau", "Mật khẩu hết hạn sau N ngày (0 = không hết hạn)", "int"),
    "force_change_on_reset": (True, "mat_khau", "Bắt đổi mật khẩu khi đăng nhập bằng mật khẩu tạm / tài khoản mới", "bool"),
    "inactive_days": (90, "tai_khoan", "Số ngày không đăng nhập thì xếp vào 'tài khoản không hoạt động'", "int"),
    "work_hour_start": (6, "bao_mat", "Giờ bắt đầu làm việc (đăng nhập ngoài giờ sẽ được cảnh báo)", "int"),
    "work_hour_end": (20, "bao_mat", "Giờ kết thúc làm việc", "int"),
    "upload_max_mb": (20, "chung", "Dung lượng tối đa tệp đính kèm (MB)", "int"),
}
GROUP_NAMES = {"tinh": "Thông tin tỉnh triển khai", "chung": "Thông tin chung", "phien": "Phiên đăng nhập", "bao_mat": "Bảo mật đăng nhập",
               "mat_khau": "Chính sách mật khẩu", "tai_khoan": "Tài khoản"}


def get_setting(db: Session, key: str):
    row = db.get(SystemSetting, key)
    return row.value if row is not None else DEFAULTS[key][0]


def all_settings(db: Session) -> list[dict]:
    stored = {r.key: r for r in db.scalars(select(SystemSetting))}
    out = []
    for k, (default, group, desc, typ) in DEFAULTS.items():
        r = stored.get(k)
        out.append({"key": k, "value": r.value if r else default, "default": default, "group": group,
                    "group_name": GROUP_NAMES[group], "description": desc, "type": typ,
                    "updated_at": r.updated_at if r else None, "updated_by": r.updated_by if r else None})
    return out


def set_setting(db: Session, key: str, value, username: str | None):
    if key not in DEFAULTS:
        raise KeyError(key)
    typ = DEFAULTS[key][3]
    if typ == "int":
        value = int(value)
        if value < 0:
            raise ValueError("Giá trị không được âm")
    elif typ == "bool":
        value = bool(value)
    else:
        value = str(value)
    row = db.get(SystemSetting, key) or SystemSetting(key=key)
    row.value, row.updated_by = value, username
    db.add(row)


def check_password_policy(db: Session, pw: str) -> str | None:
    """Trả về thông báo lỗi nếu mật khẩu không đạt chính sách."""
    n = get_setting(db, "password_min_length")
    if len(pw) < n:
        return f"Mật khẩu tối thiểu {n} ký tự"
    if get_setting(db, "password_require_complex"):
        if not (any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw)
                and any(not c.isalnum() for c in pw)):
            return "Mật khẩu phải có chữ hoa, chữ thường, chữ số và ký tự đặc biệt"
    return None


def province_label(db: Session) -> str:
    """VD: 'Tỉnh Tây Ninh' – rỗng nếu chưa cấu hình."""
    name = get_setting(db, "province_name")
    return f"{get_setting(db, 'province_type')} {name}".strip() if name else ""
