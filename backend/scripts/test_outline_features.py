"""Kiểm thử các chức năng bổ sung theo đề cương – python -m scripts.test_outline_features"""
import io
import json
import sys
import urllib.error
import urllib.request

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, expect=200, binary=False):
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
        print("    ", payload[:250])
    if binary:
        return payload
    try:
        return json.loads(payload)
    except Exception:  # noqa: BLE001
        return payload


def login(u):
    return call("POST", "/auth/login", body={"username": u, "password": "123456"})["access_token"]


sk, kh, am, stp, tinh, ht, cb = (login(u) for u in ["skhcn", "khanhhau", "am01", "lanhdao.stp", "lanhdao.tinh", "truong.thcs", "cb.khanhhau"])

print("== 1. Danh mục dịch vụ / giải pháp công nghệ ==")
s = call("POST", "/services", sk, {"code": "AI_CHATBOT", "name": "Trợ lý ảo trả lời người dân (AI)", "category": "dvc", "pillar_code": "DV",
                                   "unit_types": ["hanh_chinh"], "monthly_price": 1500000})
call("POST", "/services", kh, {"code": "X", "name": "x", "category": "dvc", "unit_types": []}, expect=403)
sv = {x["code"]: x["id"] for x in call("GET", "/services", sk)}
uid_kh = call("GET", "/auth/me", kh)["user"]["unit"]["id"]
call("POST", f"/units/{uid_kh}/services", sk, {"service_id": sv["AI_CHATBOT"], "status": "dung_thu", "usage_level": 30})
d = call("GET", f"/units/{uid_kh}", kh)
usid = next(x["id"] for x in d["services"] if x["code"] == "AI_CHATBOT")
call("DELETE", f"/units/{uid_kh}/services/{usid}", sk)

print("== 2. Cơ quan hành chính cấp tỉnh (Sở) ==")
w = call("GET", "/analytics/overview", stp)
print("   Sở Tư pháp thấy", w["kpi"]["units"], "đơn vị (chính mình) – DTI", w["kpi"]["avg_dti"])
uid_stp = call("GET", "/auth/me", stp)["user"]["unit"]["id"]
print("   đề xuất cho Sở:", len(call("GET", f"/units/{uid_stp}", stp)["recommendations"]))
call("GET", f"/units/{uid_kh}", stp, expect=403)

print("== 3. Kế hoạch chăm sóc của AM ==")
pf = call("GET", "/am/portfolio", am)
u0 = pf["units"][0]["unit_id"]
r = call("POST", f"/am/care-plans/suggest?unit_id={u0}", am)
print("   gợi ý tự động:", r["created"], "hoạt động cho", pf["units"][0]["name"])
cp = call("GET", f"/am/care-plans?unit_id={u0}", am)["items"]
c0 = cp[0]
call("PUT", f"/am/care-plans/{c0['id']}", am, {**{k: c0[k] for k in ("unit_id", "activity", "title", "service_code", "planned_date", "note")},
                                                "status": "da_thuc_hien", "result": "Đã tập huấn 15 cán bộ"})
call("POST", "/am/care-plans", am, {"unit_id": uid_stp, "activity": "tu_van", "title": "x", "planned_date": "2026-12-01"}, expect=403)

print("== 4. Lập kế hoạch cải thiện từ đề xuất ==")
pl = call("GET", "/analytics/planning", kh)
gids = [g["id"] for g in pl["groups"][:3]]
p = call("POST", "/plans", kh, {"title": "Kế hoạch thử", "region_id": call("GET", "/auth/me", kh)["user"]["region"]["id"], "solution_ids": gids})
print("   kế hoạch:", p["item_count"], "hạng mục cho", p["units"], "đơn vị")
call("POST", "/plans", cb, {"title": "x", "solution_ids": gids}, expect=403)            # công chức không lập kế hoạch
item = p["items"][0]
call("PUT", f"/plans/items/{item['id']}", kh, {"responsible": "Phòng Văn hóa – Xã hội"})
mine = next((i for i in p["items"] if i["unit_name"].startswith("Trường THCS")), None)
if mine:
    call("PUT", f"/plans/items/{mine['id']}", ht, {"progress": 60})                     # đơn vị tự cập nhật tiến độ
    call("PUT", f"/plans/items/{mine['id']}", ht, {"action": "sửa nội dung"}, expect=403)
call("PUT", f"/plans/{p['id']}", kh, {"status": "ban_hanh"})
x = call("GET", f"/plans/{p['id']}/export.xlsx", kh, binary=True)
print("   xuất Excel:", len(pd.read_excel(io.BytesIO(x), sheet_name="hang_muc")), "hạng mục")
call("GET", "/plans", stp)

print("== 5. Báo cáo bổ sung ==")
t = pd.read_excel(io.BytesIO(call("GET", "/reports/tasks.xlsx", kh, binary=True)), sheet_name=None)
print("   báo cáo nhiệm vụ:", {k: len(v) for k, v in t.items()})
tr = pd.read_excel(io.BytesIO(call("GET", "/reports/trend.xlsx", tinh, binary=True)), sheet_name=None)
print("   báo cáo diễn biến:", {k: len(v) for k, v in tr.items()})

print("== 6. Đánh giá mô hình ML ==")
ev = call("GET", "/data/ml/evaluate", tinh)
print("   silhouette theo k:", [(c["k"], c["silhouette"]) for c in ev["clustering"]], "→ k tốt nhất", ev.get("best_k"))
print("   dự báo:", ev["forecast"])

print("== 7. View cho Power BI ==")
import psycopg  # noqa: E402
with psycopg.connect("postgresql://dti:dtipass@localhost:5433/dti_platform") as c:
    for v in ["v_bi_dti", "v_bi_tru_cot", "v_bi_tieu_chi", "v_bi_dia_ban", "v_bi_canh_bao", "v_bi_nhiem_vu"]:
        n = c.execute(f"SELECT count(*) FROM gold.{v}").fetchone()[0]
        print(f"   gold.{v}: {n} dòng")
print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
