"""Kiểm thử chức năng quản trị 'xem dưới vai trò' (impersonation) – python -m scripts.test_impersonation"""
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, expect=200):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method)
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
        FAILS.append(path)
        print("    ", payload[:200])
    return json.loads(payload) if payload[:1] in b"{[" else payload


def login(u):
    return call("POST", "/auth/login", body={"username": u, "password": "123456"})["access_token"]


admin, kh = login("admin"), login("khanhhau")
users = {u["username"]: u["id"] for u in call("GET", "/admin/users?size=100", admin)["items"]}
call("POST", f"/auth/impersonate/{users['vanthu.khanhhau']}", kh, expect=403)        # người thường không được
imp = call("POST", f"/auth/impersonate/{users['vanthu.khanhhau']}", admin)
t = imp["access_token"]
me = call("GET", "/auth/me", t)
print("   đang xem dưới:", me["user"]["username"], "| bởi:", me["impersonated_by"]["username"], "| quyền:", me["permissions"])
w = call("GET", "/workspace", t)
print("   bàn làm việc của văn thư:", {q["title"]: len(q["items"]) for q in w["queues"]})
aid = w["queues"][0]["items"][0]["assignment_id"]
call("POST", f"/tasks/assignments/{aid}/action", t, {"action": "tiep_nhan"}, expect=403)  # chỉ xem
call("POST", "/notifications/read-all", t, expect=403)
call("GET", "/admin/users", t, expect=403)                                                # mang quyền của văn thư
call("POST", f"/auth/impersonate/{users['khanhhau']}", t, expect=403)                   # không lồng phiên (bị chặn ở chế độ chỉ xem)
back = call("POST", "/auth/stop-impersonate", t)
print("   trở về:", back["user"]["username"])
call("GET", "/admin/users", back["access_token"])
call("POST", "/auth/stop-impersonate", admin, expect=400)
logs = call("GET", "/admin/audit-logs?action=impersonate_start", admin)["items"]
print("   nhật ký:", [(x["username"], x["detail"]) for x in logs[:1]])
print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
