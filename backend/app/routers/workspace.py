"""Bàn làm việc theo chức danh: mỗi người chỉ thấy các hàng đợi công việc thuộc phần việc của mình.

  Văn thư         → Văn bản đến chờ tiếp nhận
  Lãnh đạo/TP     → Chờ phân công · Chờ duyệt & ký · Báo cáo cấp dưới chờ xác nhận
  Công chức / GV  → Việc đang xử lý · Bị trả về
  Lãnh đạo tỉnh/VP→ Báo cáo chờ xác nhận · Đơn vị quá hạn
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Assessment, DTIScore, Period, Task, TaskAssignment, Unit, User
from ..security import get_current_user, perms_of
from .tasks import STATUS_NAMES
from .assessments import STATUS as ASTATUS, _review_scope

router = APIRouter(prefix="/api/workspace", tags=["Bàn làm việc"])


def _item(a: TaskAssignment, t: Task) -> dict:
    return {"assignment_id": a.id, "task_id": t.id, "code": t.code, "title": t.title, "deadline": t.deadline,
            "assigner": t.assigner.name, "unit_id": a.unit_id, "unit_name": a.unit.name, "unit_type": a.unit.unit_type,
            "unit_category": a.unit.category, "status": a.status, "status_name": STATUS_NAMES[a.status],
            "progress": a.progress, "handler_dept": a.handler_dept, "handler_name": a.handler_name,
            "report_doc_number": a.report_doc_number, "report_note": a.report_note, "return_reason": a.return_reason,
            "priority": t.priority, "is_cascaded": t.parent_assignment_id is not None,
            "overdue": a.status not in ("hoan_thanh", "khong_tiep_nhan") and t.deadline < date.today(),
            "days_left": (t.deadline - date.today()).days}


@router.get("")
def workspace(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    perms = perms_of(user)
    is_admin = user.role.code == "admin"
    queues: list[dict] = []

    def mine(statuses):
        if not user.unit_id:
            return []
        rows = db.execute(select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                          .where(TaskAssignment.unit_id == user.unit_id, TaskAssignment.status.in_(statuses))
                          .order_by(Task.deadline)).all()
        return [_item(a, t) for a, t in rows]

    if "task.receive" in perms and not is_admin:
        queues.append({"key": "receive", "title": "Văn bản đến chờ tiếp nhận", "color": "#2563eb", "action": "tiep_nhan",
                       "hint": "Kiểm tra văn bản, tiếp nhận vào sổ hoặc không tiếp nhận (ghi rõ lý do)",
                       "items": mine(["chua_tiep_nhan"])})
    if "task.dispatch" in perms and not is_admin:
        items = [i for i in mine(["dang_xu_ly", "tra_lai"]) if not i["handler_name"]]
        queues.append({"key": "dispatch", "title": "Chờ phân công xử lý", "color": "#7c3aed", "action": "phan_cong",
                       "hint": "Giao phòng / công chức chủ trì", "items": items})
    if "task.process" in perms and not is_admin:
        work = mine(["dang_xu_ly"])
        queues.append({"key": "process", "title": "Việc đang xử lý", "color": "#0891b2", "action": "trinh",
                       "hint": "Cập nhật tiến độ, hoàn thiện dự thảo rồi trình lãnh đạo", "items": work})
        queues.append({"key": "returned", "title": "Bị trả lại / yêu cầu bổ sung", "color": "#dc2626", "action": "trinh",
                       "hint": "Bổ sung theo ý kiến rồi trình lại", "items": mine(["tra_lai"])})
    if "task.review" in perms and not is_admin:
        queues.append({"key": "review", "title": "Dự thảo chờ kiểm tra", "color": "#9333ea", "action": "kiem_tra",
                       "hint": "Kiểm tra nội dung, thể thức dự thảo của công chức rồi trình lãnh đạo ký (hoặc trả về)",
                       "items": mine(["cho_kiem_tra"])})
    if "task.sign" in perms and not is_admin:
        queues.append({"key": "sign", "title": "Văn bản chờ ký duyệt", "color": "#ea580c", "action": "ky_duyet",
                       "hint": "Xem dự thảo, ký duyệt (văn thư sẽ cấp số, phát hành) hoặc trả về xử lý", "items": mine(["cho_duyet"])})
    if "task.issue" in perms and "task.sign" not in perms and not is_admin:
        queues.append({"key": "issue", "title": "Văn bản đã ký chờ cấp số, phát hành", "color": "#0d9488", "action": "phat_hanh",
                       "hint": "Cấp số, ngày ban hành, đăng ký sổ văn bản đi và phát hành đến cơ quan giao",
                       "items": mine(["cho_phat_hanh"])})
    if "task.confirm" in perms:
        stmt = (select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                .where(TaskAssignment.status == "da_bao_cao").order_by(Task.deadline))
        if user.role.data_scope != "all":
            stmt = stmt.where(Task.assigner_unit_id == user.unit_id)
        else:  # cấp tỉnh: báo cáo gửi lên các cơ quan cấp tỉnh
            stmt = stmt.where(Task.assigner_unit_id.in_(select(Unit.id).where(Unit.level == "tinh", Unit.unit_type == "hanh_chinh")))
        rows = db.execute(stmt.limit(200)).all()
        queues.append({"key": "confirm", "title": "Báo cáo cấp dưới chờ kiểm tra, xác nhận", "color": "#16a34a", "action": "xac_nhan",
                       "hint": "Kiểm tra kết quả: xác nhận hoàn thành hoặc trả lại yêu cầu bổ sung", "items": [_item(a, t) for a, t in rows]})
    if "task.assign" in perms and user.unit_id:
        stmt = (select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                .where(Task.assigner_unit_id == user.unit_id, TaskAssignment.status.notin_(["hoan_thanh", "khong_tiep_nhan"]),
                       Task.deadline < date.today()).order_by(Task.deadline))
        queues.append({"key": "overdue", "title": "Đơn vị cấp dưới quá hạn – cần đôn đốc", "color": "#b91c1c", "action": None,
                       "hint": "Các lượt giao do đơn vị bạn phát hành đã quá hạn", "items": [_item(a, t) for a, t in db.execute(stmt.limit(100)).all()]})

    # ---- quy trình đánh giá mức độ chuyển đổi số của kỳ hiện tại
    cur = db.scalar(select(Period).where(Period.is_current))
    if cur and not is_admin:
        def a_item(a: Assessment) -> dict:
            return {"assessment_id": a.id, "unit_id": a.unit_id, "unit_name": a.unit.name, "unit_type": a.unit.unit_type,
                    "status": a.status, "status_name": ASTATUS[a.status], "self_score": a.self_score,
                    "submitted_at": a.submitted_at, "review_note": a.review_note, "title": f"Phiếu tự đánh giá {cur.name}"}
        if perms & {"assess.prepare", "assess.submit"} and user.unit_id:
            a = db.scalar(select(Assessment).where(Assessment.unit_id == user.unit_id, Assessment.period_id == cur.id))
            todo = a is None or a.status in ("nhap", "tra_lai")
            if todo and not cur.is_locked:
                item = a_item(a) if a else {"assessment_id": None, "unit_id": user.unit_id, "unit_name": user.unit.name,
                                            "status": "nhap", "status_name": "Chưa lập", "title": f"Phiếu tự đánh giá {cur.name}"}
                queues.append({"key": "assess_self", "title": "Tự đánh giá mức độ chuyển đổi số", "color": "#4f46e5",
                               "action": "assess_submit" if "assess.submit" in perms else "assess_prepare", "kind": "assessment",
                               "hint": ("Duyệt phiếu do chuyên viên lập rồi nộp cơ quan thẩm định" if "assess.submit" in perms
                                        else "Khai giá trị từng tiêu chí kèm minh chứng, báo lãnh đạo duyệt nộp"),
                               "items": [item]})
        if "assess.review" in perms:
            rows = db.scalars(_review_scope(db, user).where(Assessment.period_id == cur.id, Assessment.status == "da_nop")
                              .order_by(Assessment.submitted_at)).unique().all()
            queues.append({"key": "assess_review", "title": "Phiếu tự đánh giá chờ thẩm định", "color": "#be185d",
                           "action": "assess_review", "kind": "assessment",
                           "hint": "Đối chiếu minh chứng, chấp nhận/điều chỉnh từng tiêu chí, phê duyệt hoặc yêu cầu giải trình",
                           "items": [a_item(a) for a in rows]})

        if "assess.publish" in perms and not cur.published_at:
            cnt = dict(db.execute(select(Assessment.status, func.count()).where(Assessment.period_id == cur.id)
                                  .group_by(Assessment.status)).all())
            queues.append({"key": "assess_publish", "title": "Kết quả đánh giá chờ công bố", "color": "#0f766e",
                           "action": "assess_publish", "kind": "assessment",
                           "hint": "Khi các phiếu đã nộp được thẩm định xong, ban hành quyết định công bố kết quả chính thức của kỳ",
                           "items": [{"assessment_id": None, "unit_name": f"{cnt.get('da_tham_dinh', 0)} phiếu đã thẩm định · "
                                                                        f"{cnt.get('da_nop', 0)} chờ thẩm định",
                                      "status": "da_nop" if cnt.get("da_nop") else "da_tham_dinh",
                                      "status_name": "Chưa đủ điều kiện công bố" if cnt.get("da_nop") else "Sẵn sàng công bố",
                                      "title": f"Kết quả đánh giá chuyển đổi số {cur.name}"}]})

    my_unit = None
    if user.unit_id:
        p = db.scalar(select(Period).where(Period.is_current))
        d = db.get(DTIScore, (user.unit_id, p.id)) if p else None
        my_unit = {"id": user.unit_id, "name": user.unit.name, "dti": d.score if d else None, "level": d.level if d else None,
                   "rank": d.rank_overall if d else None, "delta": d.delta_prev if d else None}
    return {"role": {"code": user.role.code, "name": user.role.name, "level": user.role.level},
            "unit": my_unit, "queues": queues,
            "total_pending": sum(len(q["items"]) for q in queues if q["key"] != "overdue")}
