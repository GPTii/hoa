"""Kiểm thử: che thông tin hệ thống theo vai trò, thông báo, đôn đốc, đính kèm, số đến, tự khai báo hạ tầng.

    python -m scripts.test_privacy_features      (backend đang chạy ở cổng 8000)
"""
import datetime as dt
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, expect=200, raw=None, ctype="application/json"):
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
        print("    ", payload[:250])
    try:
        return json.loads(payload)
    except Exception:  # noqa: BLE001
        return payload


def login(u):
    return call("POST", "/auth/login", body={"username": u, "password": "123456"})["access_token"]


def upload(token, path, filename, content, fields=None, expect=200):
    b = "----dti"
    parts = b""
    for k, v in (fields or {}).items():
        parts += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    parts += f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
    parts += content + f"\r\n--{b}--\r\n".encode()
    return call("POST", path, token, raw=parts, ctype=f"multipart/form-data; boundary={b}", expect=expect)


admin, kh, vt, cb, tinh, truong = (login(u) for u in ["admin", "khanhhau", "vanthu.khanhhau", "cb.khanhhau", "lanhdao.tinh", "truong.thcs"])

print("== Thông tin hệ thống chỉ quản trị xem ==")
call("GET", "/auth/roles-guide", None, expect=401)
call("GET", "/auth/roles-guide", kh, expect=403)
call("GET", "/auth/roles-guide", admin)
call("GET", "/analytics/clusters", kh, expect=403)
call("GET", "/framework", kh, expect=403)
call("GET", "/data/batches", tinh, expect=403)
demo = call("GET", "/auth/demo-accounts")
print("   demo-accounts chỉ có:", sorted(demo[0].keys()))
mr = call("GET", "/auth/my-role", vt)
assert "can" not in mr and "cannot" not in mr, "my-role không được trả danh sách quyền"
print("   văn thư – việc:", mr["duties"], "| phạm vi:", mr["scope_name"], mr["scope_detail"])

print("== Thông báo & số đến ==")
n = call("GET", "/notifications", vt)
print("   văn thư có", n["unread"], "thông báo chưa đọc:", [i["title"][:50] for i in n["items"][:2]])
w = call("GET", "/workspace", vt)
a = w["queues"][0]["items"][0]
r = call("POST", f"/tasks/assignments/{a['assignment_id']}/action", vt, {"action": "tiep_nhan"})
print("   số đến được cấp:", r["incoming_no"])
nk = call("GET", "/notifications", kh)
print("   chủ tịch nhận:", nk["items"][0]["title"][:70])
call("POST", "/notifications/read-all", kh)
print("   sau khi đọc hết:", call("GET", "/notifications", kh)["unread"])

print("== Đôn đốc ==")
root = call("POST", "/tasks", tinh, {"title": "Kiểm thử đôn đốc", "deadline": str(dt.date.today() + dt.timedelta(days=3)),
                                      "lead_unit_ids": [call("GET", "/auth/me", kh)["user"]["unit"]["id"]]})
aid = root["assignments"][0]["id"]
call("POST", f"/tasks/assignments/{aid}/remind", tinh, {"note": "Đề nghị khẩn trương"})
call("POST", f"/tasks/assignments/{aid}/remind", cb, {"note": "x"}, expect=403)
print("   văn thư nhận:", [i["title"][:40] for i in call("GET", "/notifications", vt)["items"] if i["kind"] == "don_doc"][:1])

print("== Đính kèm ==")
upload(tinh, f"/tasks/{root['id']}/attachments", "van_ban_giao.pdf", b"%PDF-1.4 test")
upload(cb, f"/tasks/{root['id']}/attachments", "x.pdf", b"%PDF", expect=403)                     # không phải cơ quan giao
upload(cb, f"/tasks/{root['id']}/attachments", "bao_cao.pdf", b"%PDF-1.4 bc", {"assignment_id": aid})
upload(tinh, f"/tasks/{root['id']}/attachments", "virus.exe", b"MZ", expect=400)
att = call("GET", f"/tasks/{root['id']}/attachments", kh)
print("   tệp:", [(x["kind"], x["file_name"]) for x in att])
call("GET", f"/tasks/attachments/{att[0]['id']}/download", kh)

print("== Tự khai báo hạ tầng ==")
uid = call("GET", "/auth/me", truong)["user"]["unit"]["id"]
call("PUT", f"/units/{uid}/infra", truong, {"computers": 60, "internet_mbps": 300, "has_wifi": True, "has_firewall": True})
call("PUT", f"/units/{uid + 1}/infra", truong, {"computers": 1}, expect=403)
call("PUT", f"/units/{uid}/infra", vt, {"computers": 1}, expect=403)

print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
