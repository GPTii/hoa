"""Kiểm thử 8 nhóm chức năng quản trị – python -m scripts.test_admin_ops (backend chạy ở cổng 8000)."""
import io
import json
import sys
import urllib.error
import urllib.request

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, expect=200, raw=None, ctype="application/json", headers=None, binary=False):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", ctype)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as r:
            code, payload = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, payload = e.code, e.read()
    ok = code == expect
    print(f"{'OK ' if ok else 'ERR'} {method} {path} → {code}")
    if not ok:
        FAILS.append(path)
        print("    ", payload[:250])
    if binary:
        return payload
    try:
        return json.loads(payload)
    except Exception:  # noqa: BLE001
        return payload


def login(u, pw="123456", expect=200):
    r = call("POST", "/auth/login", body={"username": u, "password": pw}, expect=expect)
    return r.get("access_token") if isinstance(r, dict) else None


def upload(token, path, filename, content, expect=200):
    b = "----dti"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode() + content + f"\r\n--{b}--\r\n".encode()
    return call("POST", path, token, raw=body, ctype=f"multipart/form-data; boundary={b}", expect=expect)


admin, qt = login("admin"), login("qt.khanhhau")
uid = {u["username"]: u["id"] for u in call("GET", "/admin/users?size=100", admin)["items"]}

print("\n== 1. Bảo mật tài khoản ==")
for i in range(4):
    login("gv.thcs", "sai_mat_khau", expect=401)
login("gv.thcs", "sai_mat_khau", expect=423)                 # lần 5 → khóa tạm
login("gv.thcs", expect=423)                                   # đúng mật khẩu vẫn bị chặn khi đang khóa
call("POST", f"/admin/users/{uid['gv.thcs']}/unlock", qt)     # quản trị xã mở khóa
gv = login("gv.thcs")
sess = call("GET", "/admin/sessions", admin)
print("   phiên đang hoạt động:", len(sess), "| có IP/thiết bị:", bool(sess[0]["ip"]))
call("POST", f"/admin/users/{uid['gv.thcs']}/revoke-sessions", qt)
call("GET", "/auth/me", gv, expect=401)                        # đã bị buộc đăng xuất
tmp = call("POST", f"/admin/users/{uid['gv.thcs']}/reset-password", qt)["temporary_password"]
gv = login("gv.thcs", tmp)
call("GET", "/workspace", gv, expect=403)                      # phải đổi mật khẩu trước
print("   me.must_change_password =", call("GET", "/auth/me", gv)["must_change_password"])
call("POST", "/auth/change-password", gv, {"old_password": tmp, "new_password": "123"}, expect=400)
call("POST", "/auth/change-password", gv, {"old_password": tmp, "new_password": "123456"})
call("GET", "/workspace", gv)
call("POST", "/auth/logout", gv)
call("GET", "/auth/me", gv, expect=401)

print("\n== 2. Nhập / xuất hàng loạt ==")
tpl = call("GET", "/admin/users/template.xlsx", qt, binary=True)
df = pd.read_excel(io.BytesIO(tpl), sheet_name=None)
print("   mẫu có sheet:", list(df.keys()), "| vai trò quản trị xã được gán:", len(df["vai_tro"]))
units = df["don_vi"]
xa = units[units.ma_don_vi.str.startswith("HC.")].ma_don_vi.iloc[0]
truong = units[units.ma_don_vi.str.startswith("GD.")].ma_don_vi.iloc[0]
imp = pd.DataFrame([
    {"ten_dang_nhap": "vt2.khanhhau", "ho_ten": "Văn thư 2", "ma_vai_tro": "van_thu_xa", "ma_don_vi": xa},
    {"ten_dang_nhap": "ht.mamnon", "ho_ten": "Hiệu trưởng MN", "ma_vai_tro": "hieu_truong", "ma_don_vi": truong},
    {"ten_dang_nhap": "khanhhau", "ho_ten": "Trùng", "ma_vai_tro": "van_thu_xa", "ma_don_vi": xa},
    {"ten_dang_nhap": "x.tinh", "ho_ten": "Vượt cấp", "ma_vai_tro": "lanh_dao_tinh", "ma_don_vi": xa},
    {"ten_dang_nhap": "x.sai", "ho_ten": "Sai đơn vị", "ma_vai_tro": "hieu_truong", "ma_don_vi": xa},
])
buf = io.BytesIO()
imp.to_excel(buf, index=False)
r = upload(qt, "/admin/users/import?dry_run=true", "tk.xlsx", buf.getvalue())
print("   kiểm tra trước:", r["valid"], "/", r["total"], "hợp lệ →", [(x["username"], x["message"][:40]) for x in r["rows"] if not x["ok"]])
r = upload(qt, "/admin/users/import?dry_run=false", "tk.xlsx", buf.getvalue())
print("   đã tạo:", r["created"], "tài khoản, mật khẩu tạm:", [x["password"] for x in r["rows"] if x["password"]])
xl = call("GET", "/admin/users/export.xlsx", qt, binary=True)
print("   xuất Excel:", len(pd.read_excel(io.BytesIO(xl))), "tài khoản trong phạm vi phường")
ina = call("GET", "/admin/users/inactive", qt)
print("   không hoạt động >", ina["days"], "ngày:", len(ina["items"]))
call("POST", "/admin/users/bulk-lock", qt, {"ids": [uid["admin"]]}, expect=403)   # ngoài phạm vi

print("\n== 3. Chuyển giao ==")
pv = call("GET", f"/admin/users/{uid['cb.khanhhau']}/handover", qt)
print("   cb.khanhhau đang xử lý:", len(pv["tasks"]), "việc | người nhận khả dụng:", [c["username"] for c in pv["candidates"]])
new_id = next(u["id"] for u in call("GET", "/admin/users?q=vt2", qt)["items"])
target = pv["candidates"][0]["id"] if pv["candidates"] else new_id
hv = call("POST", f"/admin/users/{uid['cb.khanhhau']}/handover", qt, {"to_user_id": target, "lock_account": True, "note": "Chuyển công tác"})
print("   bàn giao:", hv)
login("cb.khanhhau", expect=403)

print("\n== 4. Cấu hình, kỳ, địa bàn ==")
st = call("GET", "/admin/settings", admin)
print("   số tham số:", len(st))
call("PUT", "/admin/settings", qt, {"session_minutes": 60}, expect=403)
call("PUT", "/admin/settings", admin, {"password_min_length": 8, "demo_mode": True})
call("POST", f"/admin/users/{new_id}/reset-password", qt)
call("PUT", "/admin/settings", admin, {"password_min_length": 6})
call("PUT", "/admin/settings", admin, {"khong_ton_tai": 1}, expect=400)
pers = call("GET", "/admin/periods", admin)
prev = next(p for p in pers if not p["is_current"])
call("PUT", f"/admin/periods/{prev['id']}", admin, {"is_locked": True})
cur = next(p for p in pers if p["is_current"])
call("PUT", f"/admin/periods/{cur['id']}", admin, {"is_locked": True}, expect=400)
sk = login("skhcn")
call("POST", f"/data/recompute?period={prev['code']}", sk, expect=409)
call("PUT", f"/admin/periods/{prev['id']}", admin, {"is_locked": False})
call("POST", "/admin/regions", admin, {"code": "R99", "name": "Xã Thử Nghiệm", "type": "xa", "population": 1000})
print("   số địa bàn:", len(call("GET", "/admin/regions", admin)))

print("\n== 5. Thông báo hệ thống ==")
r = call("POST", "/admin/announcements", admin, {"title": "Bảo trì hệ thống 22h tối nay", "body": "Dự kiến 30 phút", "target": "xa", "severity": "warning"})
print("   gửi tới", r["recipients"], "người dùng cấp xã")
kh = login("khanhhau")
print("   chủ tịch phường nhận:", [n["title"] for n in call("GET", "/notifications", kh)["items"] if n["kind"] == "he_thong"][:1])
call("POST", "/admin/announcements", qt, {"title": "x"}, expect=403)

print("\n== 6. Giám sát & sao lưu ==")
mon = call("GET", "/admin/monitor", admin)
print("   CSDL", round(mon["db_size"] / 1e6, 1), "MB | schema:", {s["schema"]: s["rows"] for s in mon["schemas"]}, "| lỗi 24h:", mon["errors_24h"])
b = call("POST", "/admin/backups", admin)
print("   sao lưu:", b)
bl = call("GET", "/admin/backups", admin)
call("GET", f"/admin/backups/{bl[0]['id']}/download", admin, binary=True)
call("GET", "/admin/monitor", qt, expect=403)

print("\n== 7. Nhật ký nâng cao ==")
a = call("GET", "/admin/audit?action=login_failed&size=5", admin)
print("   login_failed:", a["total"], "| các loại hành động:", len(a["actions"]))
call("GET", "/admin/audit/export.xlsx?date_from=2026-01-01", admin, binary=True)
al = call("GET", "/admin/security-alerts", admin)
print("   cảnh báo bảo mật:", [(x["type"], x["username"]) for x in al[:4]])
print("   quản trị xã thấy", len(call("GET", "/admin/security-alerts", qt)), "cảnh báo (trong địa bàn)")

print("\n== 8. Khóa API tích hợp ==")
k = call("POST", "/admin/api-keys", admin, {"name": "LGSP Tây Ninh", "scopes": ["dti.read", "metrics.push"]})
key = k["key"]
call("GET", "/integration/dti", None, expect=401)
d = call("GET", "/integration/dti", None, headers={"X-API-Key": key})
print("   LGSP đọc DTI kỳ", d["period"], ":", len(d["items"]), "đơn vị")
call("GET", "/integration/units", None, headers={"X-API-Key": key}, expect=403)          # không có scope
p = call("POST", "/integration/metrics", None, {"period": cur["code"], "metrics": [
    {"unit_code": "HC.R03", "criterion": "DV01", "value": "95%"}, {"unit_code": "HC.X", "criterion": "DV01", "value": "1"}]},
    headers={"X-API-Key": key})
print("   đẩy số liệu:", {k_: p[k_] for k_ in ("batch_id", "valid", "rejected")})
call("POST", f"/admin/api-keys/{k['id']}/revoke", admin)
call("GET", "/integration/dti", None, headers={"X-API-Key": key}, expect=401)

print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
