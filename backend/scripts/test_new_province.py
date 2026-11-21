"""Kiểm thử luồng triển khai tỉnh mới (chạy sau: python -m scripts.seed --blank --province "Bình Phước" --admin-password "Admin@2026x").

    python -m scripts.test_new_province
"""
import io
import json
import sys
import urllib.error
import urllib.request

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, expect=200, raw=None, ctype="application/json", binary=False):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", ctype)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            code, payload = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, payload = e.code, e.read()
    ok = code == expect
    print(f"{'OK ' if ok else 'ERR'} {method} {path} → {code}")
    if not ok:
        FAILS.append(path)
        print("    ", payload[:300])
    if binary:
        return payload
    try:
        return json.loads(payload)
    except Exception:  # noqa: BLE001
        return payload


def upload(token, path, content, filename="f.xlsx"):
    b = "----dti"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode() + content + f"\r\n--{b}--\r\n".encode()
    return call("POST", path, token, raw=body, ctype=f"multipart/form-data; boundary={b}")


def status(t):
    s = call("GET", "/admin/setup/status", t)
    print(f"   TIẾN ĐỘ {s['done']}/{s['total']} – {s['province']}: " + " | ".join(("✔ " if x["done"] else "✗ ") + x["title"] for x in s["steps"]))
    return s


cfg = call("GET", "/auth/public-config")
print("   public-config:", cfg["province_label"], "| demo:", cfg["demo_mode"], "| MK tối thiểu:", cfg["password_min_length"])
assert call("GET", "/auth/demo-accounts") == []
r = call("POST", "/auth/login", body={"username": "admin", "password": "Admin@2026x"})
t = r["access_token"]
print("   admin phải đổi mật khẩu:", r["must_change_password"])
call("GET", "/admin/setup/status", t, expect=403)
call("POST", "/auth/change-password", t, {"old_password": "Admin@2026x", "new_password": "yeu"}, expect=400)    # chính sách mạnh
call("POST", "/auth/change-password", t, {"old_password": "Admin@2026x", "new_password": "BinhPhuoc@2026"})
status(t)

# bước 2: danh mục từ file mẫu (bổ sung thêm một xã)
tpl = pd.read_excel(io.BytesIO(call("GET", "/admin/catalog/template.xlsx", t, binary=True)), sheet_name=None)
print("   file mẫu danh mục có sheet:", list(tpl))
reg = pd.concat([tpl["dia_ban"], pd.DataFrame([{"ma": "X003", "ten": "Xã Lộc Ninh", "loai": "xa", "dan_so": 40000, "dien_tich_km2": 120}])])
units = pd.concat([tpl["don_vi"], pd.DataFrame([
    {"ma_don_vi": "HC.S09", "ten_don_vi": "Sở Giáo dục và Đào tạo", "phan_loai": "so_nganh", "ma_don_vi_cap_tren": "HC.T01"},
    {"ma_don_vi": "HC.X003", "ten_don_vi": "UBND Xã Lộc Ninh", "phan_loai": "ubnd_xa", "ma_dia_ban": "X003"},
    {"ma_don_vi": "GD.X003.THCS1", "ten_don_vi": "Trường THCS Lộc Ninh", "phan_loai": "thcs", "ma_dia_ban": "X003", "ma_don_vi_cap_tren": "HC.X003"},
    {"ma_don_vi": "GD.SAI", "ten_don_vi": "Trường lỗi", "phan_loai": "tieu_hoc", "ma_dia_ban": ""},          # lỗi: thiếu địa bàn
    {"ma_don_vi": "HC.SAI2", "ten_don_vi": "Đơn vị lỗi", "phan_loai": "khong_co"},                            # lỗi: phân loại
])])
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    reg.to_excel(w, index=False, sheet_name="dia_ban")
    units.to_excel(w, index=False, sheet_name="don_vi")
dry = upload(t, "/admin/catalog/import?dry_run=true", buf.getvalue())
print("   kiểm tra:", dry["regions"]["new"], "địa bàn,", dry["units"]["new"], "đơn vị mới | lỗi:", dry["units"]["errors"])
res = upload(t, "/admin/catalog/import?dry_run=false", buf.getvalue())
res2 = upload(t, "/admin/catalog/import?dry_run=false", buf.getvalue())
print("   nhập lại lần 2 → cập nhật:", res2["regions"]["update"], "địa bàn,", res2["units"]["update"], "đơn vị (không tạo trùng)")

# bước 5: tài khoản
roles = {r_["code"]: r_["id"] for r_ in call("GET", "/admin/roles", t)}
ids = {u["code"]: u["id"] for u in call("GET", "/admin/units?size=50", t)["items"]}
call("POST", "/admin/users", t, {"username": "lanhdao.tinh", "full_name": "Lãnh đạo tỉnh", "password": "LanhDao@2026",
                                 "role_id": roles["lanh_dao_tinh"], "unit_id": ids["HC.T01"]})
call("POST", "/admin/users", t, {"username": "qt.locninh", "full_name": "Quản trị xã Lộc Ninh", "password": "QuanTri@2026",
                                 "role_id": roles["quan_tri_xa"], "unit_id": ids["HC.X003"]})
# bước 3, 6
call("PUT", "/admin/settings", t, {"demo_mode": False})
s = status(t)
assert s["done"] >= 5, "Phải xong ít nhất 5/7 bước (tiêu chí & dữ liệu do Sở KH&CN)"
call("GET", "/analytics/overview", t, expect=403)   # admin vẫn không xem nghiệp vụ
print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
