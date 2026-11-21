"""Kiểm thử nhanh API (smoke test) với nhiều vai trò – chạy khi backend đang chạy ở cổng 8000.

    python -m scripts.smoke_test
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, raw=False, expect=200):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
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
        FAILS.append((path, code, payload[:300]))
        print("    ", payload[:300])
    return payload if raw else (json.loads(payload) if payload and payload[:1] in b"{[" else payload)


def login(u):
    return call("POST", "/auth/login", body={"username": u, "password": "123456"})["access_token"]


admin = login("admin")
tinh0, skh0, am0 = login("lanhdao.tinh"), login("skhcn"), login("am01")
call("POST", "/auth/login", body={"username": "admin", "password": "sai"}, expect=401)
# mỗi nhóm API do đúng vai trò nghiệp vụ gọi
for who, paths in [
    (tinh0, ["/auth/me", "/regions", "/periods", "/units?size=5", "/units/options", "/services", "/solutions",
             "/analytics/overview", "/analytics/ranking?size=5", "/analytics/regions", "/analytics/alerts?size=5",
             "/analytics/priority", "/analytics/planning", "/analytics/clusters", "/analytics/compare?unit_ids=1,2,20",
             "/tasks?size=3", "/tasks/stats", "/tasks/1", "/analytics/planning/1/units"]),
    (skh0, ["/framework", "/data/batches", "/data/batches/1/rejected", "/data/batches/1/raw"]),
    (admin, ["/admin/users", "/admin/roles", "/admin/permissions", "/admin/audit-logs", "/admin/stats", "/admin/units?size=5"]),
    (am0, ["/am/portfolio"]),
]:
    for p_ in paths:
        call("GET", p_, who)
# quản trị hệ thống tách biệt nghiệp vụ: không xem số liệu, không xử lý văn bản
for p_ in ["/analytics/overview", "/units?size=5", "/units/20", "/tasks?size=3", "/data/batches", "/framework", "/am/portfolio",
           "/workspace"]:
    call("GET", p_, admin, expect=200 if p_ == "/workspace" else 403)
d = call("GET", "/units/20", tinh0)
print("   unit 20:", d["unit"]["name"], d["dti"], len(d["recommendations"]), "đề xuất")
call("GET", "/reports/dti.xlsx", tinh0, raw=True)
call("GET", "/data/template", skh0, raw=True)

# phạm vi dữ liệu
kh = login("khanhhau")
o = call("GET", "/analytics/overview", kh)
print("   khanhhau thấy", o["kpi"]["units"], "đơn vị")
call("GET", "/units/1", kh, expect=403)
call("GET", "/admin/users", kh, expect=403)
truong = login("truong.thcs")
print("   truong thấy", call("GET", "/analytics/overview", truong)["kpi"]["units"], "đơn vị")
am = login("am01")
pf = call("GET", "/am/portfolio", am)
print("   am01:", pf["summary"])
call("POST", "/data/recompute", am, expect=403)

# luồng nhiệm vụ: phường giao trường → trường tiếp nhận → báo cáo → phường xác nhận
me_kh = call("GET", "/auth/me", kh)["user"]
units = call("GET", f"/units?size=50&region_id={me_kh['region']['id']}&unit_type=giao_duc", kh)["items"]
school = next(u for u in units if u["category"] == "thcs")
import datetime as dt
t = call("POST", "/tasks", kh, {"title": "Kiểm thử: báo cáo hạ tầng CNTT", "doc_number": "99/UBND-TEST",
                                 "deadline": str(dt.date.today() + dt.timedelta(days=5)), "lead_unit_ids": [school["id"]]})
aid = t["assignments"][0]["id"]
call("POST", f"/tasks/assignments/{aid}/action", kh, {"action": "tiep_nhan"}, expect=403)  # phường không tiếp nhận thay trường
call("POST", f"/tasks/assignments/{aid}/action", truong, {"action": "tiep_nhan", "handler_name": "GV Tin học"})
r = call("POST", f"/tasks/assignments/{aid}/action", truong, {"action": "ky_duyet", "note": "Đã cập nhật"})  # HT kiêm văn thư: ký → tự cấp số
print("   trường ký & phát hành:", r["status"], r.get("report_doc_number"))
assert r["status"] == "da_bao_cao" and r.get("report_doc_number", "").endswith("/BC-THCS"), r
call("POST", f"/tasks/assignments/{aid}/action", truong, {"action": "xac_nhan"}, expect=403)  # trường không tự xác nhận
r = call("POST", f"/tasks/assignments/{aid}/action", kh, {"action": "xac_nhan"})
print("   trạng thái cuối:", r["status_name"])

# pipeline: upload file dạng dài có lỗi
sk = login("skhcn")
f = Path(__file__).resolve().parents[2] / "sample_data" / "cap_nhat_bo_sung_dang_dai.csv"
boundary = "----dti"
body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{f.name}\"\r\nContent-Type: text/csv\r\n\r\n").encode() \
    + f.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
req = urllib.request.Request(BASE + "/data/upload", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
req.add_header("Authorization", f"Bearer {sk}")
res = json.loads(urllib.request.urlopen(req).read())
print("   upload:", res["batch"]["message"], "| gold:", res["gold"])
print("   lỗi:", [x["reason"] for x in call("GET", f"/data/batches/{res['batch']['id']}/rejected", sk)])
call("POST", "/data/sync", sk)
# ---- luồng liên thông 3 cấp: Tỉnh → Phường Khánh Hậu → các trường
print("\n== Luồng 3 cấp Tỉnh → Phường → Trường ==")
tinh = login("lanhdao.tinh")
D = lambda n: str(dt.date.today() + dt.timedelta(days=n))  # noqa: E731
root = call("POST", "/tasks", tinh, {"title": "Kiểm thử 3 cấp: báo cáo CĐS trường học", "doc_number": "1/UBND-TEST",
                                     "deadline": D(10), "lead_unit_ids": [me_kh["unit"]["id"]]})
pa = root["assignments"][0]["id"]
vt, tp, cb, vp = login("vanthu.khanhhau"), login("tp.khanhhau"), login("cb.khanhhau"), login("vp.ubndtinh")
call("POST", "/tasks", vp, {"title": "x", "deadline": D(3), "lead_unit_ids": [1]}, expect=403)  # VP chỉ theo dõi, đôn đốc
call("POST", f"/tasks/assignments/{pa}/cascade", kh, {"deadline": D(5), "lead_unit_ids": [school["id"]]}, expect=400)  # chưa tiếp nhận
call("POST", f"/tasks/assignments/{pa}/action", kh, {"action": "tiep_nhan"}, expect=403)  # lãnh đạo không làm thay văn thư
call("POST", f"/tasks/assignments/{pa}/action", vt, {"action": "tiep_nhan"})                # văn thư tiếp nhận
call("POST", f"/tasks/assignments/{pa}/action", vt, {"action": "phan_cong", "handler_dept": "x"}, expect=403)
call("POST", f"/tasks/assignments/{pa}/cascade", vt, {"deadline": D(5), "lead_unit_ids": [school["id"]]}, expect=403)
call("POST", f"/tasks/assignments/{pa}/action", kh, {"action": "phan_cong", "handler_dept": "Phòng Văn hóa – Xã hội"})
call("POST", f"/tasks/assignments/{pa}/action", tp, {"action": "phan_cong", "handler_name": "Công chức CĐS"})
call("POST", f"/tasks/assignments/{pa}/action", cb, {"action": "bao_cao", "report_doc_number": "1"}, expect=403)  # công chức không ký
sg = login("sgddt")
print("   Sở GD&ĐT thấy", call("GET", "/analytics/overview", sg)["kpi"]["units"], "đơn vị (chỉ trường học)")
subs = call("GET", f"/tasks/assignments/{pa}/subordinates", kh)
print("   trường thuộc phường:", [s["name"] for s in subs] if isinstance(subs, list) else subs)
call("POST", f"/tasks/assignments/{pa}/cascade", kh, {"deadline": D(15), "lead_unit_ids": [subs[0]["id"]]}, expect=400)  # hạn vượt cấp trên
call("POST", f"/tasks/assignments/{pa}/cascade", kh, {"deadline": D(5), "lead_unit_ids": [1]}, expect=400)  # không phải cấp dưới
call("POST", f"/tasks/assignments/{pa}/cascade", truong, {"deadline": D(5), "lead_unit_ids": [subs[0]["id"]]}, expect=403)
child = call("POST", f"/tasks/assignments/{pa}/cascade", kh, {"deadline": D(5), "lead_unit_ids": [s["id"] for s in subs]})
print("   nhiệm vụ con:", child["code"], "giao cho", child["total_units"], "trường")
call("POST", f"/tasks/assignments/{pa}/action", kh, {"action": "bao_cao", "report_doc_number": "9/BC-UBND"}, expect=400)  # trường chưa xong
rid = {r["code"]: r["id"] for r in call("GET", "/admin/roles", admin)}
ht = {}
for ca in child["assignments"]:
    if ca["unit_id"] != school["id"]:
        un = f"ht.test{ca['unit_id']}"
        call("POST", "/admin/users", admin, {"username": un, "full_name": "Hiệu trưởng (test)", "password": "123456",
                                             "role_id": rid["hieu_truong"], "unit_id": ca["unit_id"]})
        tok = login(un)
        call("GET", "/workspace", tok, expect=403)  # tài khoản mới: phải đổi mật khẩu trước
        call("POST", "/auth/change-password", tok, {"old_password": "123456", "new_password": "MatKhau@2026"})
        ht[ca["unit_id"]] = tok
for ca in child["assignments"]:
    who = truong if ca["unit_id"] == school["id"] else ht[ca["unit_id"]]
    call("POST", f"/tasks/assignments/{ca['id']}/action", who, {"action": "tiep_nhan"})
    call("POST", f"/tasks/assignments/{ca['id']}/action", who, {"action": "bao_cao", "report_doc_number": "1/BC-TRUONG"})
    call("POST", f"/tasks/assignments/{ca['id']}/action", tinh, {"action": "xac_nhan"}, expect=200)  # cấp tỉnh được đôn đốc thay
tr = call("GET", f"/tasks/{root['id']}/tree", tinh)
print("   tiến độ phường sau khi trường xong:", tr["units"][0]["progress"], "% | cấp con:", len(tr["units"][0]["children"]["units"]), "trường")
call("POST", f"/tasks/assignments/{pa}/action", cb, {"action": "trinh", "note": "Dự thảo báo cáo tổng hợp"})       # công chức trình
call("POST", f"/tasks/assignments/{pa}/action", kh, {"action": "tra_ve_xu_ly", "note": "Bổ sung số liệu THCS"})  # lãnh đạo trả về
r = call("POST", f"/tasks/assignments/{pa}/action", cb, {"action": "trinh", "note": "Đã bổ sung"})
assert r["status"] == "cho_kiem_tra", r["status"]                                                 # qua trưởng phòng
call("POST", f"/tasks/assignments/{pa}/action", kh, {"action": "kiem_tra"}, expect=403)           # lãnh đạo không kiểm tra thay TP
call("POST", f"/tasks/assignments/{pa}/action", vt, {"action": "phat_hanh"}, expect=400)          # chưa ký
r = call("POST", f"/tasks/assignments/{pa}/action", tp, {"action": "kiem_tra", "note": "Đúng thể thức"})
assert r["status"] == "cho_duyet", r["status"]
call("POST", f"/tasks/assignments/{pa}/action", tp, {"action": "ky_duyet"}, expect=403)           # TP không ký
r = call("POST", f"/tasks/assignments/{pa}/action", kh, {"action": "ky_duyet", "note": "Tổng hợp 100% trường"})
assert r["status"] == "cho_phat_hanh", r["status"]                                                # chờ văn thư
call("POST", f"/tasks/assignments/{pa}/action", vp, {"action": "xac_nhan"}, expect=400)           # chưa phát hành
r = call("POST", f"/tasks/assignments/{pa}/action", vt, {"action": "phat_hanh"})
print("   văn thư cấp số đi:", r.get("report_doc_number"), "| số đi", r.get("outgoing_no"))
assert r["status"] == "da_bao_cao" and r.get("outgoing_no"), r
reg = call("GET", "/tasks/registers/di", vt)
print("   sổ văn bản đi:", len(reg), "văn bản, mới nhất:", reg[-1]["so_ky_hieu"] if reg else None)
call("GET", "/tasks/registers/den", vt)
call("GET", "/tasks/registers/di/export", vt, raw=True)
r = call("POST", f"/tasks/assignments/{pa}/action", vp, {"action": "xac_nhan"})  # VP UBND tỉnh xác nhận thay UBND tỉnh
print("   trạng thái nhiệm vụ gốc tại phường:", r["status_name"])

# ---- quản trị phân cấp
print("\n== Quản trị phân cấp ==")
qt = login("qt.khanhhau")
ctx = call("GET", "/admin/context", qt)
print("   quản trị xã được gán:", [r["name"] for r in ctx["roles"]], "| số đơn vị:", len(ctx["units"]))
us = call("GET", "/admin/users?size=100", qt)
print("   quản trị xã thấy", us["total"], "tài khoản:", [u["username"] for u in us["items"]])
role_id = rid
kh_unit = me_kh["unit"]["id"]
vt2 = call("POST", "/admin/users", qt, {"username": "test.vt2", "full_name": "Văn thư 2", "password": "123456",
                                  "role_id": role_id["van_thu_xa"], "unit_id": kh_unit})
call("POST", "/admin/users", qt, {"username": "test.x", "full_name": "x", "password": "123456",
                                  "role_id": role_id["lanh_dao_tinh"], "unit_id": kh_unit}, expect=403)   # vai trò cấp tỉnh
call("POST", "/admin/users", qt, {"username": "test.y", "full_name": "y", "password": "123456",
                                  "role_id": role_id["quan_tri_xa"], "unit_id": kh_unit}, expect=403)     # tạo quản trị khác
call("POST", "/admin/users", qt, {"username": "test.z", "full_name": "z", "password": "123456",
                                  "role_id": role_id["van_thu_xa"], "unit_id": 1}, expect=403)            # đơn vị ngoài địa bàn
call("POST", "/admin/users", qt, {"username": "test.w", "full_name": "w", "password": "123456",
                                  "role_id": role_id["hieu_truong"], "unit_id": kh_unit}, expect=400)     # hiệu trưởng phải thuộc trường
admin_id = next(u["id"] for u in call("GET", "/admin/users?q=lanhdao", admin)["items"])
call("POST", f"/admin/users/{admin_id}/reset-password", qt, expect=403)
call("GET", "/admin/permissions", qt, expect=403)
print("   mật khẩu tạm:", call("POST", f"/admin/users/{vt2['id']}/reset-password", qt)["temporary_password"])

# ---- bàn làm việc theo chức danh
print("\n== Bàn làm việc ==")
for un in ["vanthu.khanhhau", "khanhhau", "tp.khanhhau", "cb.khanhhau", "truong.thcs", "vp.ubndtinh", "skhcn"]:
    w = call("GET", "/workspace", login(un))
    print(f"   {un:16s}", {q["title"]: len(q["items"]) for q in w["queues"]})

print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
