"""Kiểm thử quy trình TỰ ĐÁNH GIÁ → THẨM ĐỊNH → CÔNG BỐ và phân quyền từng bước (chạy sau seed, backend ở cổng 8000)."""
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api"
FAILS = []


def call(method, path, token=None, body=None, expect=200):
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
        print("    ", payload[:300].decode("utf8", "replace"))
    return json.loads(payload) if payload and payload[:1] in b"{[" else payload


def login(u):
    return call("POST", "/auth/login", body={"username": u, "password": "123456"})["access_token"]


cb, kh, tp, admin = login("cb.khanhhau"), login("khanhhau"), login("tp.khanhhau"), login("admin")
skh, sgd, tinh, gv, ht = login("skhcn"), login("sgddt"), login("lanhdao.tinh"), login("gv.thcs"), login("truong.thcs")

print("== 1. Phường tự đánh giá ==")
call("GET", "/assessments/mine", tp, expect=403)        # trưởng phòng không lập phiếu
call("GET", "/assessments/mine", admin, expect=403)     # quản trị không làm nghiệp vụ
a = call("GET", "/assessments/mine", cb)
print("   phiếu", a["id"], a["status_name"], f"{a['filled']}/{a['total']} tiêu chí đã khai; can_submit =", a["can_submit"])
assert a["can_edit"] and not a["can_submit"]
items = [{"criterion_id": i["criterion_id"], "value_raw": i["value_raw"] or ("Có" if i["metric_type"] == "boolean" else "50"),
          "evidence": i["evidence"] or f"Minh chứng {i['code']}"} for i in a["items"]]
bad = call("PUT", f"/assessments/{a['id']}/items", cb, [{"criterion_id": a["items"][0]["criterion_id"], "value_raw": "abc"}])
print("   giá trị sai bị từ chối:", bad["errors"])
assert not bad["ok"]
call("POST", f"/assessments/{a['id']}/submit", cb, {}, expect=403)   # công chức không nộp
r = call("PUT", f"/assessments/{a['id']}/items", cb, items)
print("   đã lưu, điểm tự chấm ước tính:", r["self_score"])
call("PUT", f"/assessments/{a['id']}/items", login("vanthu.khanhhau"), items, expect=403)
r = call("POST", f"/assessments/{a['id']}/submit", kh, {"note": "Kính gửi Sở KH&CN thẩm định"})
assert r["status"] == "da_nop", r
call("PUT", f"/assessments/{a['id']}/items", cb, items, expect=400)  # đã nộp: khóa sửa

print("== 2. Thẩm định ==")
lst = call("GET", "/assessments?status=da_nop", skh)
types = {x["unit_type"] for x in lst["items"]}
print("   Sở KH&CN thấy", len(lst["items"]), "phiếu chờ thẩm định, loại hình:", types)
assert types == {"hanh_chinh"}, "Sở KH&CN chỉ thẩm định cơ quan hành chính khi có Sở GD&ĐT"
lg = call("GET", "/assessments?status=da_nop", sgd)
print("   Sở GD&ĐT thấy", len(lg["items"]), "phiếu, loại hình:", {x["unit_type"] for x in lg["items"]})
assert {x["unit_type"] for x in lg["items"]} == {"giao_duc"}
call("POST", f"/assessments/{a['id']}/review", sgd, {"action": "approve"}, expect=403)  # ngoài phạm vi
call("POST", f"/assessments/{a['id']}/review", kh, {"action": "approve"}, expect=403)   # đơn vị không tự thẩm định
call("POST", f"/assessments/{a['id']}/review", skh, {"action": "return"}, expect=400)   # trả lại phải có lý do
r = call("POST", f"/assessments/{a['id']}/review", skh, {"action": "return", "note": "Bổ sung minh chứng tiêu chí DV01"})
assert r["status"] == "tra_lai"
w = call("GET", "/workspace", cb)
print("   bàn làm việc công chức:", [(q["title"], q["items"][0]["status_name"]) for q in w["queues"] if q["key"] == "assess_self"])
call("PUT", f"/assessments/{a['id']}/items", cb, items)
call("POST", f"/assessments/{a['id']}/submit", kh, {"note": "Đã bổ sung"})
crit0 = a["items"][0]
r = call("POST", f"/assessments/{a['id']}/review", skh, {"action": "approve", "note": "Đạt",
                                                         "items": [{"criterion_id": crit0["criterion_id"],
                                                                    "reviewer_value": "Không" if crit0["metric_type"] == "boolean" else "10",
                                                                    "reviewer_note": "Minh chứng chưa thuyết phục"}]})
print("   phê duyệt:", r["status_name"], "| DTI sau thẩm định:", r["final_score"], "| điều chỉnh", r["adjusted"], "tiêu chí")
assert r["status"] == "da_tham_dinh" and r["final_score"] is not None and r["adjusted"] == 1
b = call("GET", "/data/batches", skh)
src = b[0] if isinstance(b, list) else b["items"][0]
print("   lô Bronze mới nhất:", src.get("source_type"), "–", src.get("file_name"))

print("== 3. Trường: giáo viên lập, hiệu trưởng nộp, Sở GD&ĐT thẩm định ==")
t = call("GET", "/assessments/mine", gv)
print("   phiếu trường:", t["status_name"])
r = call("POST", f"/assessments/{t['id']}/review", sgd, {"action": "approve"})
assert r["status"] == "da_tham_dinh"

print("== 4. Công bố ==")
call("POST", "/assessments/publish/2026-Q4", skh, {"decision": "1/QĐ-UBND"}, expect=403)  # chỉ UBND tỉnh
call("POST", "/assessments/publish/2026-Q3", tinh, {"decision": "1/QĐ-UBND"}, expect=400)  # đã công bố
s = call("GET", "/assessments", tinh)
print("   tổng hợp kỳ:", s["counts"])
if s["counts"]["da_nop"]:
    call("POST", "/assessments/publish/2026-Q4", tinh, {"decision": "1/QĐ-UBND"}, expect=400)  # còn phiếu chưa thẩm định
o = call("GET", "/analytics/overview", tinh)
print("   tổng quan kỳ hiện hành: chính thức =", o["published"], "| kỳ trước:", call("GET", "/analytics/overview?period=2026-Q3", tinh)["published"])
assert not o["published"]

print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if not FAILS else f"{len(FAILS)} lỗi")
