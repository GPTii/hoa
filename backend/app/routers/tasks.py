"""Giao & theo dõi nhiệm vụ chuyển đổi số – liên thông nhiều cấp theo mô hình chính quyền địa phương 2 cấp (dùng chung cho mọi tỉnh).

Luồng 3 cấp (Tỉnh → Xã/Phường → Trường học):
 1. UBND tỉnh / Sở ban hành văn bản giao nhiệm vụ cho UBND xã, phường (chủ trì, phối hợp, hạn xử lý).
 2. UBND xã: văn thư TIẾP NHẬN (hoặc KHÔNG TIẾP NHẬN + lý do) → lãnh đạo phân công phòng/công chức.
 3. UBND xã GIAO TIẾP cho các trường trên địa bàn (nhiệm vụ con, hạn ≤ hạn cấp trên).
 4. Trường tiếp nhận → xử lý → BÁO CÁO lên xã → xã KIỂM TRA, XÁC NHẬN hoặc TRẢ LẠI.
 5. Khi các trường đã xong, xã TỔNG HỢP và BÁO CÁO lên tỉnh → tỉnh XÁC NHẬN hoàn thành.
 Nhận văn bản ≠ hoàn thành; gửi báo cáo ≠ hoàn thành → chỉ cơ quan giao xác nhận mới đóng nhiệm vụ.
"""
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..config import settings
from ..models import Notification, Task, TaskAssignment, TaskAttachment, TaskLog, Unit, User
from ..security import audit, perms_of, require, scoped_unit_ids

router = APIRouter(prefix="/api/tasks", tags=["Giao & theo dõi nhiệm vụ"])

STATUS_NAMES = {"chua_tiep_nhan": "Chưa tiếp nhận", "khong_tiep_nhan": "Không tiếp nhận", "dang_xu_ly": "Đang xử lý",
                "cho_kiem_tra": "Chờ trưởng phòng kiểm tra", "cho_duyet": "Chờ lãnh đạo ký", "cho_phat_hanh": "Chờ văn thư phát hành",
                "da_bao_cao": "Đã báo cáo – chờ xác nhận", "hoan_thanh": "Hoàn thành", "tra_lai": "Trả lại – bổ sung"}
CLOSED = ("hoan_thanh", "khong_tiep_nhan")
WORKING = {"dang_xu_ly", "tra_lai"}
DRAFTING = {"cho_kiem_tra", "cho_duyet"}

# Quy trình theo Nghị định 30/2020/NĐ-CP về công tác văn thư:
#   VĂN BẢN ĐẾN: văn thư tiếp nhận, đăng ký (cấp số đến) → trình lãnh đạo → lãnh đạo cho ý kiến chỉ đạo, phân công
#                → giải quyết, theo dõi, đôn đốc
#   VĂN BẢN ĐI (báo cáo kết quả): công chức soạn thảo, trình → trưởng phòng kiểm tra → lãnh đạo KÝ
#                → văn thư CẤP SỐ, ngày ban hành, đăng ký sổ văn bản đi, PHÁT HÀNH → cơ quan giao kiểm tra, xác nhận
# hành động → (trạng thái được phép, trạng thái mới, phía thực hiện, quyền cần có)
TRANSITIONS = {
    "tiep_nhan": ({"chua_tiep_nhan"}, "dang_xu_ly", "receiver", ("task.receive",)),
    "khong_tiep_nhan": ({"chua_tiep_nhan"}, "khong_tiep_nhan", "receiver", ("task.receive",)),
    "phan_cong": (WORKING, None, "receiver", ("task.dispatch",)),
    "cap_nhat": (WORKING, None, "receiver", ("task.process", "task.dispatch")),
    "trinh": (WORKING, "cho_kiem_tra", "receiver", ("task.process",)),          # → cho_duyet nếu không có trưởng phòng
    "kiem_tra": ({"cho_kiem_tra"}, "cho_duyet", "receiver", ("task.review",)),
    "tra_ve_xu_ly": (DRAFTING, "dang_xu_ly", "receiver", ("task.review", "task.sign")),
    "ky_duyet": (WORKING | DRAFTING, "cho_phat_hanh", "receiver", ("task.sign",)),  # → da_bao_cao nếu người ký kiêm phát hành
    "phat_hanh": ({"cho_phat_hanh"}, "da_bao_cao", "receiver", ("task.issue",)),
    "xac_nhan": ({"da_bao_cao"}, "hoan_thanh", "assigner", ("task.confirm",)),
    "tra_lai": ({"da_bao_cao"}, "tra_lai", "assigner", ("task.confirm",)),
}
TRANSITIONS["bao_cao"] = TRANSITIONS["ky_duyet"]  # tên cũ, giữ tương thích
ACTION_NAMES = {"tiep_nhan": "Tiếp nhận, vào sổ văn bản đến", "khong_tiep_nhan": "Không tiếp nhận", "phan_cong": "Phân công xử lý",
                "cap_nhat": "Cập nhật tiến độ", "trinh": "Trình dự thảo", "kiem_tra": "Kiểm tra, trình lãnh đạo ký",
                "tra_ve_xu_ly": "Trả về xử lý lại", "ky_duyet": "Ký duyệt văn bản", "bao_cao": "Ký duyệt văn bản",
                "phat_hanh": "Cấp số & phát hành", "xac_nhan": "Xác nhận hoàn thành", "tra_lai": "Trả lại yêu cầu bổ sung"}
ABBR = {"ubnd_tinh": "UBND", "van_phong": "VP", "so_nganh": "SO", "ubnd_xa": "UBND", "thpt": "THPT", "thcs": "THCS",
        "tieu_hoc": "TH", "mam_non": "MN"}


UPLOAD_DIR = Path(__file__).resolve().parents[2] / settings.upload_dir
UPLOAD_DIR.mkdir(exist_ok=True)


def unit_users(db: Session, unit_id: int, need: tuple[str, ...]) -> list[int]:
    """Người dùng đang hoạt động của một đơn vị có ít nhất một quyền trong `need` – người nhận thông báo."""
    users = db.scalars(select(User).where(User.unit_id == unit_id, User.is_active)).unique().all()
    return [u.id for u in users if {p.code for p in u.role.permissions} & set(need)]


def notify(db: Session, user_ids: list[int], kind: str, title: str, task_id: int | None = None, body: str | None = None):
    for uid in dict.fromkeys(user_ids):
        db.add(Notification(user_id=uid, kind=kind, title=title[:300], body=body, task_id=task_id))


def notify_new_assignment(db: Session, t: Task, unit_ids: list[int]):
    for uid in unit_ids:
        notify(db, unit_users(db, uid, ("task.receive",)), "van_ban_den", f"Văn bản đến: {t.title}", t.id,
               f"{t.assigner.name} · {t.doc_number or ''} · hạn {t.deadline:%d/%m/%Y}")


def child_summary(db: Session, assignment_ids: list[int]) -> dict[int, dict]:
    """Tóm tắt nhiệm vụ con (giao tiếp) theo từng lượt giao của cấp trên."""
    if not assignment_ids:
        return {}
    out: dict[int, dict] = {}
    rows = db.execute(select(Task.parent_assignment_id, Task.id, Task.deadline, TaskAssignment.status)
                      .join(TaskAssignment, TaskAssignment.task_id == Task.id)
                      .where(Task.parent_assignment_id.in_(assignment_ids), TaskAssignment.role == "chu_tri")).all()
    for pid, tid, dl, st in rows:
        s = out.setdefault(pid, {"task_ids": set(), "total": 0, "done": 0, "reported": 0, "overdue": 0})
        s["task_ids"].add(tid)
        s["total"] += 1
        s["done"] += st in CLOSED
        s["reported"] += st == "da_bao_cao"
        s["overdue"] += st not in CLOSED and dl < date.today()
    for s in out.values():
        s["task_ids"] = sorted(s["task_ids"])
    return out


def a_out(a: TaskAssignment, deadline: date, child: dict | None = None) -> dict:
    overdue = a.status not in CLOSED and deadline < date.today()
    late_done = a.status == "hoan_thanh" and a.confirmed_at and a.confirmed_at.date() > deadline
    return {"id": a.id, "unit_id": a.unit_id, "unit_name": a.unit.name, "unit_type": a.unit.unit_type,
            "unit_category": a.unit.category, "role": a.role, "status": a.status,
            "status_name": STATUS_NAMES[a.status], "received_at": a.received_at, "reject_reason": a.reject_reason,
            "handler_dept": a.handler_dept, "handler_name": a.handler_name, "progress": a.progress,
            "report_doc_number": a.report_doc_number, "report_note": a.report_note, "reported_at": a.reported_at,
            "confirmed_at": a.confirmed_at, "return_reason": a.return_reason, "overdue": overdue, "incoming_no": a.incoming_no,
            "leader_opinion": a.leader_opinion, "reviewed_by": a.reviewed_by, "signed_by": a.signed_by, "signed_at": a.signed_at,
            "outgoing_no": a.outgoing_no, "issued_by": a.issued_by, "issued_at": a.issued_at,
            "late_done": bool(late_done), "child": child}


def t_out(t: Task, scope: list[int] | None = None, children: dict | None = None) -> dict:
    asg = [a for a in t.assignments if scope is None or a.unit_id in scope or t.assigner_unit_id in scope]
    lead = [a for a in t.assignments if a.role == "chu_tri"]
    children = children or {}
    return {"id": t.id, "code": t.code, "title": t.title, "content": t.content, "doc_number": t.doc_number,
            "doc_date": t.doc_date, "doc_type": t.doc_type, "assigner_unit_id": t.assigner_unit_id,
            "assigner_name": t.assigner.name, "priority": t.priority, "require_report": t.require_report,
            "deadline": t.deadline, "pillar_code": t.pillar_code, "created_at": t.created_at,
            "parent_assignment_id": t.parent_assignment_id, "is_cascaded": t.parent_assignment_id is not None,
            "total_units": len(lead), "done_units": sum(1 for a in lead if a.status == "hoan_thanh"),
            "overdue_units": sum(1 for a in lead if a.status not in CLOSED and t.deadline < date.today()),
            "cascaded_units": sum(1 for a in lead if a.id in children),
            "assignments": [a_out(a, t.deadline, children.get(a.id)) for a in asg]}


@router.get("")
def list_tasks(box: str = "all", status: str | None = None, q: str | None = None, level: str | None = None,
               page: int = 1, size: int = 15, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    """box = all | giao (đơn vị mình giao) | nhan (đơn vị mình nhận). level = goc (chỉ nhiệm vụ gốc) | giao_tiep."""
    scope = scoped_unit_ids(db, user)
    stmt = select(Task)
    if box == "giao":
        stmt = stmt.where(Task.assigner_unit_id.in_(scope or [-1]) if scope is not None else Task.assigner_unit_id.isnot(None))
    elif box == "nhan":
        sub = select(TaskAssignment.task_id)
        if scope is not None:
            sub = sub.where(TaskAssignment.unit_id.in_(scope or [-1]))
        stmt = stmt.where(Task.id.in_(sub))
    elif scope is not None:
        sub = select(TaskAssignment.task_id).where(TaskAssignment.unit_id.in_(scope or [-1]))
        stmt = stmt.where(or_(Task.id.in_(sub), Task.assigner_unit_id.in_(scope or [-1])))
    if level == "goc":
        stmt = stmt.where(Task.parent_assignment_id.is_(None))
    elif level == "giao_tiep":
        stmt = stmt.where(Task.parent_assignment_id.isnot(None))
    if status:
        sub = select(TaskAssignment.task_id).where(TaskAssignment.status == status)
        if scope is not None:
            sub = sub.where(TaskAssignment.unit_id.in_(scope or [-1]))
        stmt = stmt.where(Task.id.in_(sub))
    if q:
        stmt = stmt.where(or_(Task.title.ilike(f"%{q}%"), Task.doc_number.ilike(f"%{q}%"), Task.code.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Task.created_at.desc(), Task.id.desc()).offset((page - 1) * size).limit(size)).all()
    children = child_summary(db, [a.id for t in rows for a in t.assignments])
    return {"total": total, "items": [t_out(t, scope, children) for t in rows]}


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    scope = scoped_unit_ids(db, user)
    stmt = select(TaskAssignment.status, Task.deadline, TaskAssignment.unit_id).join(Task, Task.id == TaskAssignment.task_id)
    if scope is not None:
        stmt = stmt.where(TaskAssignment.unit_id.in_(scope or [-1]))
    by_status = {k: 0 for k in STATUS_NAMES}
    overdue = 0
    for st, dl, _ in db.execute(stmt):
        by_status[st] += 1
        if st not in CLOSED and dl < date.today():
            overdue += 1
    return {"by_status": [{"status": k, "name": STATUS_NAMES[k], "count": v} for k, v in by_status.items()], "overdue": overdue}


def _can_see(t: Task, scope: list[int] | None) -> bool:
    return scope is None or t.assigner_unit_id in scope or any(a.unit_id in scope for a in t.assignments)


def _root_of(db: Session, t: Task) -> Task:
    while t.parent_assignment_id:
        t = db.get(TaskAssignment, t.parent_assignment_id).task
    return t


@router.get("/{tid}")
def get_task(tid: int, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404)
    scope = scoped_unit_ids(db, user)
    if not _can_see(t, scope):
        raise HTTPException(403, "Nhiệm vụ nằm ngoài phạm vi")
    logs = db.execute(select(TaskLog, User.full_name).outerjoin(User, User.id == TaskLog.user_id)
                      .where(TaskLog.task_id == tid).order_by(TaskLog.id)).all()
    d = t_out(t, scope, child_summary(db, [a.id for a in t.assignments]))
    d["logs"] = [{"id": l.id, "assignment_id": l.assignment_id, "action": l.action, "note": l.note, "user": n,
                  "created_at": l.created_at} for l, n in logs]
    d["can_confirm"] = scope is None or t.assigner_unit_id in scope
    if t.parent_assignment_id:
        pa = db.get(TaskAssignment, t.parent_assignment_id)
        d["parent"] = {"task_id": pa.task_id, "code": pa.task.code, "title": pa.task.title, "assigner_name": pa.task.assigner.name,
                       "deadline": pa.task.deadline, "assignment_id": pa.id, "status_name": STATUS_NAMES[pa.status]}
    root = _root_of(db, t)
    d["root_task_id"] = root.id
    return d


@router.get("/{tid}/tree")
def task_tree(tid: int, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    """Sơ đồ luồng liên thông từ nhiệm vụ gốc: Cơ quan giao → đơn vị nhận → (giao tiếp) → đơn vị cấp dưới..."""
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404)
    scope = scoped_unit_ids(db, user)
    root = _root_of(db, t)
    if not _can_see(t, scope):
        raise HTTPException(403)

    def node_task(task: Task, depth: int) -> dict:
        lead = [a for a in task.assignments if scope is None or a.unit_id in scope or task.assigner_unit_id in scope]
        kids = {c.parent_assignment_id: c for c in db.scalars(select(Task).where(
            Task.parent_assignment_id.in_([a.id for a in lead] or [-1])))}
        return {"task_id": task.id, "code": task.code, "title": task.title, "assigner": task.assigner.name,
                "deadline": task.deadline, "depth": depth,
                "units": [{**a_out(a, task.deadline), "children": node_task(kids[a.id], depth + 1) if a.id in kids else None}
                          for a in lead]}
    return node_task(root, 0)


class TaskIn(BaseModel):
    title: str
    content: str | None = None
    doc_number: str | None = None
    doc_date: date | None = None
    doc_type: str = "cong_van"
    assigner_unit_id: int | None = None
    priority: str = "thuong"
    require_report: bool = True
    deadline: date
    pillar_code: str | None = None
    lead_unit_ids: list[int]
    coord_unit_ids: list[int] = []


def _new_code(db: Session) -> str:
    n = db.scalar(select(func.count(Task.id))) + 1
    return f"NV-{date.today().year}-{n:04d}"


@router.post("")
def create_task(body: TaskIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("task.assign"))):
    assigner = body.assigner_unit_id or user.unit_id
    if not assigner:
        raise HTTPException(400, "Chưa xác định cơ quan giao nhiệm vụ")
    scope = scoped_unit_ids(db, user)
    if scope is not None and assigner not in scope:
        raise HTTPException(403, "Không thể giao nhiệm vụ thay đơn vị khác")
    if not body.lead_unit_ids:
        raise HTTPException(400, "Cần chọn ít nhất một đơn vị chủ trì")
    if body.deadline < date.today():
        raise HTTPException(400, "Hạn xử lý không được trước ngày hiện tại")
    t = Task(code=_new_code(db), created_by=user.id, assigner_unit_id=assigner,
             **body.model_dump(exclude={"lead_unit_ids", "coord_unit_ids", "assigner_unit_id"}))
    db.add(t)
    db.flush()
    for uid in dict.fromkeys(body.lead_unit_ids):
        db.add(TaskAssignment(task_id=t.id, unit_id=uid, role="chu_tri"))
    for uid in dict.fromkeys(body.coord_unit_ids):
        if uid not in body.lead_unit_ids:
            db.add(TaskAssignment(task_id=t.id, unit_id=uid, role="phoi_hop"))
    db.add(TaskLog(task_id=t.id, user_id=user.id, action="giao_nhiem_vu",
                   note=f"Phát hành {body.doc_number or ''} – giao {len(body.lead_unit_ids)} đơn vị chủ trì"))
    db.flush()
    db.refresh(t)
    notify_new_assignment(db, t, list(dict.fromkeys(body.lead_unit_ids + body.coord_unit_ids)))
    audit(db, user, "create", "task", t.id, {"title": t.title}, request)
    db.commit()
    db.refresh(t)
    return t_out(t)


class CascadeIn(BaseModel):
    title: str | None = None
    content: str | None = None
    doc_number: str | None = None
    deadline: date
    lead_unit_ids: list[int]


@router.get("/assignments/{aid}/subordinates")
def subordinates(aid: int, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    """Đơn vị cấp dưới có thể nhận giao tiếp: trường học do UBND xã quản lý / trên địa bàn xã."""
    a = db.get(TaskAssignment, aid)
    if not a:
        raise HTTPException(404)
    u = a.unit
    stmt = select(Unit).where(Unit.is_active, Unit.id != u.id)
    if u.category == "ubnd_xa":
        # Mầm non, Tiểu học, THCS do UBND xã quản lý; THPT do Sở GD&ĐT quản lý nên không thuộc cấp dưới của xã
        stmt = stmt.where(Unit.region_id == u.region_id, Unit.unit_type == "giao_duc", Unit.level == "xa")
    else:
        stmt = stmt.where(Unit.parent_unit_id == u.id)
    return [{"id": x.id, "name": x.name, "category": x.category} for x in db.scalars(stmt.order_by(Unit.name))]


@router.post("/assignments/{aid}/cascade")
def cascade(aid: int, body: CascadeIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("task.assign"))):
    """UBND xã giao tiếp nhiệm vụ của cấp trên xuống các trường học trên địa bàn."""
    a = db.get(TaskAssignment, aid)
    if not a:
        raise HTTPException(404)
    if user.role.code != "admin" and user.unit_id != a.unit_id:
        raise HTTPException(403, "Chỉ đơn vị được giao mới giao tiếp nhiệm vụ cho cấp dưới")
    if a.status not in ("dang_xu_ly", "tra_lai"):
        raise HTTPException(400, "Phải tiếp nhận nhiệm vụ trước khi giao tiếp cho cấp dưới")
    if body.deadline > a.task.deadline:
        raise HTTPException(400, f"Hạn của cấp dưới phải trước hoặc bằng hạn cấp trên ({a.task.deadline:%d/%m/%Y})")
    if body.deadline < date.today():
        raise HTTPException(400, "Hạn xử lý không được trước ngày hiện tại")
    allowed = {x["id"] for x in subordinates(aid, db, user)}
    bad = [u for u in body.lead_unit_ids if u not in allowed]
    if bad or not body.lead_unit_ids:
        raise HTTPException(400, "Chỉ giao tiếp được cho đơn vị cấp dưới thuộc địa bàn/quản lý của đơn vị mình")
    existing = db.scalar(select(Task).where(Task.parent_assignment_id == aid))
    if existing:  # đã giao tiếp → bổ sung đơn vị nhận
        have = {x.unit_id for x in existing.assignments}
        added = [u for u in dict.fromkeys(body.lead_unit_ids) if u not in have]
        for uid in added:
            db.add(TaskAssignment(task_id=existing.id, unit_id=uid, role="chu_tri"))
        db.add(TaskLog(task_id=existing.id, user_id=user.id, action="giao_nhiem_vu", note=f"Bổ sung {len(added)} đơn vị nhận"))
        t = existing
        notify_new_assignment(db, t, added)
    else:
        parent = a.task
        t = Task(code=_new_code(db), title=body.title or parent.title, content=body.content or parent.content,
                 doc_number=body.doc_number, doc_date=date.today(), doc_type=parent.doc_type, assigner_unit_id=a.unit_id,
                 created_by=user.id, priority=parent.priority, require_report=parent.require_report,
                 deadline=body.deadline, pillar_code=parent.pillar_code, parent_assignment_id=aid)
        db.add(t)
        db.flush()
        for uid in dict.fromkeys(body.lead_unit_ids):
            db.add(TaskAssignment(task_id=t.id, unit_id=uid, role="chu_tri"))
        db.add(TaskLog(task_id=t.id, user_id=user.id, action="giao_nhiem_vu",
                       note=f"Giao tiếp từ {parent.code} ({parent.assigner.name}) – {len(body.lead_unit_ids)} đơn vị"))
        db.add(TaskLog(task_id=parent.id, assignment_id=aid, user_id=user.id, action="giao_tiep",
                       note=f"[{a.unit.name}] giao tiếp cho {len(body.lead_unit_ids)} đơn vị cấp dưới ({t.code})"))
        db.flush()
        db.refresh(t)
        notify_new_assignment(db, t, list(dict.fromkeys(body.lead_unit_ids)))
    if not a.handler_dept:
        a.handler_dept = "Phòng Văn hóa – Xã hội"
    audit(db, user, "cascade", "task_assignment", aid, {"child_task": t.code, "units": body.lead_unit_ids}, request)
    db.commit()
    db.refresh(t)
    return t_out(t)


class ActionIn(BaseModel):
    action: str
    note: str | None = None
    progress: int | None = None
    handler_dept: str | None = None
    handler_name: str | None = None
    report_doc_number: str | None = None
    opinion: str | None = None  # ý kiến chỉ đạo (bút phê) khi phân công


def _issue(db: Session, a: TaskAssignment, user: User, now: datetime):
    """Văn thư cấp số văn bản đi (tăng dần theo đơn vị, theo năm), ngày ban hành, đăng ký sổ và phát hành."""
    last = db.scalar(select(func.max(TaskAssignment.outgoing_no)).where(
        TaskAssignment.unit_id == a.unit_id, func.extract("year", TaskAssignment.issued_at) == now.year))
    a.outgoing_no = (last or 0) + 1
    a.report_doc_number = f"{a.outgoing_no}/BC-{ABBR.get(a.unit.category, 'DV')}"
    a.issued_by, a.issued_at, a.reported_at, a.progress = user.full_name, now, now, 100


def _sync_parent_progress(db: Session, child_task: Task):
    """Khi cấp dưới hoàn thành, tiến độ của đơn vị trung gian (xã) tự cập nhật theo tỷ lệ cấp dưới đã xong."""
    if not child_task.parent_assignment_id:
        return
    pa = db.get(TaskAssignment, child_task.parent_assignment_id)
    lead = [x for x in child_task.assignments if x.role == "chu_tri"]
    if lead and pa.status in ("dang_xu_ly", "tra_lai"):
        done = sum(1 for x in lead if x.status in CLOSED)
        pa.progress = max(pa.progress, round(done * 90 / len(lead)))  # 10% còn lại: xã tổng hợp, báo cáo


@router.post("/assignments/{aid}/action")
def act(aid: int, body: ActionIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    a = db.get(TaskAssignment, aid)
    if not a:
        raise HTTPException(404)
    if body.action not in TRANSITIONS:
        raise HTTPException(400, "Hành động không hợp lệ")
    allowed_from, new_status, side, need = TRANSITIONS[body.action]
    name = ACTION_NAMES[body.action]
    if a.status not in allowed_from:
        raise HTTPException(400, f"Không thể '{name}' khi nhiệm vụ đang ở trạng thái '{STATUS_NAMES[a.status]}'")
    perms = perms_of(user)
    is_admin = user.role.code == "admin"
    if not is_admin and not perms & set(need):
        raise HTTPException(403, f"Vai trò '{user.role.name}' không có quyền '{name}'")
    if side == "receiver":
        # Chỉ chính đơn vị được giao mới thao tác (cấp trên không làm thay dù có quyền xem)
        if not is_admin and user.unit_id != a.unit_id:
            raise HTTPException(403, "Chỉ đơn vị được giao mới thực hiện được thao tác này")
    else:
        # Cơ quan giao; hoặc cấp tỉnh (Văn phòng UBND tỉnh) theo dõi, đôn đốc thay UBND tỉnh
        own = user.unit_id == a.task.assigner_unit_id or user.role.data_scope == "all"
        if not is_admin and not own:
            raise HTTPException(403, "Chỉ cơ quan giao nhiệm vụ mới xác nhận/trả lại được")

    now = datetime.now()
    if body.action == "tiep_nhan":
        a.received_at = now
        a.handler_dept, a.handler_name = body.handler_dept, body.handler_name
        # vào sổ văn bản đến: số đến tăng dần theo đơn vị, theo năm
        last = db.scalar(select(func.max(TaskAssignment.incoming_no)).where(
            TaskAssignment.unit_id == a.unit_id, func.extract("year", TaskAssignment.received_at) == now.year))
        a.incoming_no = (last or 0) + 1
    elif body.action == "phan_cong":
        if not body.handler_dept and not body.handler_name:
            raise HTTPException(400, "Chọn phòng/bộ phận hoặc người xử lý")
        a.handler_dept = body.handler_dept or a.handler_dept
        a.handler_name = body.handler_name or a.handler_name
        if body.opinion:
            a.leader_opinion = body.opinion
    elif body.action == "trinh":
        a.report_note, a.progress = body.note or a.report_note, max(a.progress, 90)
        # đơn vị có trưởng phòng (quyền kiểm tra) và người trình không phải trưởng phòng → qua bước kiểm tra
        reviewers = [i for i in unit_users(db, a.unit_id, ("task.review",)) if i != user.id]
        if not reviewers or "task.review" in perms:
            new_status = "cho_duyet"
            if "task.review" in perms:
                a.reviewed_by = user.full_name
    elif body.action == "kiem_tra":
        a.reviewed_by = user.full_name
        if body.note:
            a.report_note = body.note
    elif body.action == "tra_ve_xu_ly":
        if not body.note:
            raise HTTPException(400, "Nhập ý kiến chỉ đạo khi trả về")
        a.return_reason = body.note
    elif body.action == "khong_tiep_nhan":
        if not body.note:
            raise HTTPException(400, "Phải nhập lý do không tiếp nhận")
        a.reject_reason = body.note
    elif body.action == "cap_nhat":
        if body.progress is not None:
            a.progress = max(0, min(100, body.progress))
        if body.handler_dept:
            a.handler_dept = body.handler_dept
        if body.handler_name:
            a.handler_name = body.handler_name
    elif body.action in ("ky_duyet", "bao_cao"):
        # Đơn vị trung gian (xã) chỉ báo cáo lên trên khi các đơn vị cấp dưới đã được xác nhận xong
        child = db.scalar(select(Task).where(Task.parent_assignment_id == a.id))
        if child:
            pending = [x.unit.name for x in child.assignments if x.role == "chu_tri" and x.status not in CLOSED]
            if pending:
                raise HTTPException(400, f"Còn {len(pending)} đơn vị cấp dưới chưa hoàn thành ({', '.join(pending[:3])}"
                                         f"{'…' if len(pending) > 3 else ''}). Cần xác nhận kết quả cấp dưới trước khi tổng hợp báo cáo.")
        a.signed_by, a.signed_at = user.full_name, now
        if body.note:
            a.report_note = body.note
        a.progress = max(a.progress, 95)
        # người ký kiêm văn thư (hiệu trưởng, lãnh đạo cơ quan nhỏ) hoặc đơn vị không có văn thư → phát hành luôn
        issuers = unit_users(db, a.unit_id, ("task.issue",))
        if "task.issue" in perms or not issuers:
            _issue(db, a, user, now)
            new_status = "da_bao_cao"
    elif body.action == "phat_hanh":
        _issue(db, a, user, now)
    elif body.action == "xac_nhan":
        a.confirmed_at = now
    elif body.action == "tra_lai":
        if not body.note:
            raise HTTPException(400, "Phải nhập nội dung yêu cầu bổ sung")
        a.return_reason, a.progress = body.note, min(a.progress, 80)
    if new_status:
        a.status = new_status
    if body.action in ("xac_nhan", "khong_tiep_nhan"):
        db.flush()
        _sync_parent_progress(db, a.task)
    db.add(TaskLog(task_id=a.task_id, assignment_id=a.id, user_id=user.id, action=body.action,
                   note=f"[{a.unit.name}] {body.note or ''}".strip()))
    t = a.task
    route = {  # thông báo cho người làm bước kế tiếp
        "tiep_nhan": (a.unit_id, ("task.dispatch",), "phan_cong", f"Văn bản mới cần phân công (số đến {a.incoming_no}): {t.title}"),
        "phan_cong": (a.unit_id, ("task.process",), "phan_cong", f"Bạn được giao xử lý: {t.title}"),
        "trinh": (a.unit_id, ("task.review",) if new_status == "cho_kiem_tra" else ("task.sign",), "trinh",
                  f"Dự thảo báo cáo chờ {'kiểm tra' if new_status == 'cho_kiem_tra' else 'lãnh đạo ký'}: {t.title}"),
        "kiem_tra": (a.unit_id, ("task.sign",), "trinh", f"Dự thảo đã kiểm tra, chờ lãnh đạo ký: {t.title}"),
        "tra_ve_xu_ly": (a.unit_id, ("task.process",), "ket_qua", f"Trả về, xử lý lại: {t.title}"),
        "ky_duyet": ((t.assigner_unit_id, ("task.confirm",), "bao_cao", f"{a.unit.name} đã gửi báo cáo {a.report_doc_number}: {t.title}")
                     if new_status == "da_bao_cao" else
                     (a.unit_id, ("task.issue",), "trinh", f"Văn bản đã ký, chờ cấp số & phát hành: {t.title}")),
        "phat_hanh": (t.assigner_unit_id, ("task.confirm",), "bao_cao", f"{a.unit.name} đã gửi báo cáo {a.report_doc_number}: {t.title}"),
        "khong_tiep_nhan": (t.assigner_unit_id, ("task.confirm", "task.assign"), "ket_qua", f"{a.unit.name} KHÔNG tiếp nhận: {t.title}"),
        "xac_nhan": (a.unit_id, ("task.sign", "task.process"), "ket_qua", f"Cấp trên đã xác nhận hoàn thành: {t.title}"),
        "tra_lai": (a.unit_id, ("task.sign", "task.process"), "ket_qua", f"Cấp trên trả lại, yêu cầu bổ sung: {t.title}"),
    }.get("ky_duyet" if body.action == "bao_cao" else body.action)
    if route:
        notify(db, [i for i in unit_users(db, route[0], route[1]) if i != user.id], route[2], route[3], t.id, body.note)
    audit(db, user, body.action, "task_assignment", a.id, body.model_dump(), request)
    db.commit()
    return a_out(a, a.task.deadline)


# ---------------- đôn đốc


class RemindIn(BaseModel):
    note: str | None = None


@router.post("/assignments/{aid}/remind")
def remind(aid: int, body: RemindIn, request: Request, db: Session = Depends(get_db),
           user: User = Depends(require("task.assign", "task.confirm"))):
    """Cơ quan giao (hoặc cấp tỉnh) đôn đốc đơn vị chưa hoàn thành – gửi thông báo cho cả đơn vị."""
    a = db.get(TaskAssignment, aid)
    if not a:
        raise HTTPException(404)
    if user.role.code != "admin" and user.unit_id != a.task.assigner_unit_id and user.role.data_scope != "all":
        raise HTTPException(403, "Chỉ cơ quan giao nhiệm vụ mới đôn đốc được")
    if a.status in CLOSED or a.status == "da_bao_cao":
        raise HTTPException(400, "Đơn vị đã báo cáo hoặc nhiệm vụ đã kết thúc – không cần đôn đốc")
    days = (a.task.deadline - date.today()).days
    msg = f"ĐÔN ĐỐC: {a.task.title} – " + (f"đã quá hạn {-days} ngày" if days < 0 else f"còn {days} ngày đến hạn")
    notify(db, unit_users(db, a.unit_id, ("task.receive", "task.dispatch", "task.process", "task.sign")), "don_doc", msg,
           a.task_id, body.note)
    db.add(TaskLog(task_id=a.task_id, assignment_id=a.id, user_id=user.id, action="don_doc", note=f"[{a.unit.name}] {body.note or msg}"))
    audit(db, user, "remind", "task_assignment", aid, body.model_dump(), request)
    db.commit()
    return {"ok": True}


# ---------------- tệp đính kèm


def _attach_out(x: TaskAttachment) -> dict:
    return {"id": x.id, "assignment_id": x.assignment_id, "kind": x.kind, "file_name": x.file_name, "size": x.size,
            "created_at": x.created_at}


@router.get("/{tid}/attachments")
def list_attachments(tid: int, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    t = db.get(Task, tid)
    if not t or not _can_see(t, scoped_unit_ids(db, user)):
        raise HTTPException(404)
    return [_attach_out(x) for x in db.scalars(select(TaskAttachment).where(TaskAttachment.task_id == tid).order_by(TaskAttachment.id))]


@router.post("/{tid}/attachments")
async def upload_attachment(tid: int, request: Request, file: UploadFile = File(...), assignment_id: int | None = Form(None),
                            db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    """Cơ quan giao đính kèm văn bản giao; đơn vị nhận đính kèm báo cáo của mình."""
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404)
    perms = perms_of(user)
    admin = user.role.code == "admin"
    if assignment_id:
        a = db.get(TaskAssignment, assignment_id)
        if not a or a.task_id != tid:
            raise HTTPException(400, "Lượt giao không hợp lệ")
        if not admin and (user.unit_id != a.unit_id or not perms & {"task.process", "task.sign"}):
            raise HTTPException(403, "Chỉ đơn vị được giao mới đính kèm báo cáo")
        kind = "bao_cao"
    else:
        if not admin and (user.unit_id != t.assigner_unit_id or "task.assign" not in perms):
            raise HTTPException(403, "Chỉ cơ quan giao mới đính kèm văn bản giao")
        kind = "van_ban"
    ext = Path(file.filename).suffix.lower()
    if ext not in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".zip"}:
        raise HTTPException(400, "Chỉ nhận PDF, Word, Excel, ảnh hoặc ZIP")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Tệp vượt quá 20MB")
    stored = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / stored).write_bytes(content)
    x = TaskAttachment(task_id=tid, assignment_id=assignment_id, kind=kind, file_name=file.filename[:255], stored_name=stored,
                       size=len(content), uploaded_by=user.id)
    db.add(x)
    audit(db, user, "upload_attachment", "task", tid, {"file": file.filename, "kind": kind}, request)
    db.commit()
    return _attach_out(x)


@router.get("/attachments/{xid}/download")
def download_attachment(xid: int, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    x = db.get(TaskAttachment, xid)
    if not x:
        raise HTTPException(404)
    t = db.get(Task, x.task_id)
    if not _can_see(t, scoped_unit_ids(db, user)):
        raise HTTPException(403)
    return FileResponse(UPLOAD_DIR / x.stored_name, filename=x.file_name)


# ---------------- sổ văn bản (NĐ 30/2020: đăng ký văn bản đến, văn bản đi)


def _register(db: Session, user: User, kind: str, year: int):
    if not user.unit_id:
        raise HTTPException(400, "Tài khoản không thuộc đơn vị nào")
    col = TaskAssignment.received_at if kind == "den" else TaskAssignment.issued_at
    no = TaskAssignment.incoming_no if kind == "den" else TaskAssignment.outgoing_no
    rows = db.execute(select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                      .where(TaskAssignment.unit_id == user.unit_id, no.isnot(None), func.extract("year", col) == year)
                      .order_by(no)).all()
    if kind == "den":
        return [{"so_den": a.incoming_no, "ngay_den": a.received_at, "noi_gui": t.assigner.name, "so_ky_hieu": t.doc_number,
                 "ngay_van_ban": t.doc_date, "trich_yeu": t.title, "do_khan": "Khẩn" if t.priority == "khan" else "Thường",
                 "y_kien_chi_dao": a.leader_opinion, "don_vi_xu_ly": " · ".join(x for x in [a.handler_dept, a.handler_name] if x),
                 "han_xu_ly": t.deadline, "trang_thai": STATUS_NAMES[a.status], "task_id": t.id} for a, t in rows]
    return [{"so_di": a.outgoing_no, "ngay_ban_hanh": a.issued_at, "so_ky_hieu": a.report_doc_number,
             "trich_yeu": f"Báo cáo kết quả: {t.title}", "nguoi_ky": a.signed_by, "noi_nhan": t.assigner.name,
             "tra_loi_van_ban": t.doc_number, "nguoi_phat_hanh": a.issued_by, "trang_thai": STATUS_NAMES[a.status], "task_id": t.id}
            for a, t in rows]


@router.get("/registers/{kind}")
def register(kind: str, year: int | None = None, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    if kind not in ("den", "di"):
        raise HTTPException(404)
    return _register(db, user, kind, year or date.today().year)


@router.get("/registers/{kind}/export")
def register_export(kind: str, year: int | None = None, db: Session = Depends(get_db), user: User = Depends(require("task.view"))):
    import pandas as pd
    from .admin_ops import xlsx_response
    if kind not in ("den", "di"):
        raise HTTPException(404)
    y = year or date.today().year
    rows = _register(db, user, kind, y)
    names = ({"so_den": "Số đến", "ngay_den": "Ngày đến", "noi_gui": "Nơi gửi", "so_ky_hieu": "Số, ký hiệu", "ngay_van_ban": "Ngày văn bản",
              "trich_yeu": "Trích yếu", "do_khan": "Độ khẩn", "y_kien_chi_dao": "Ý kiến chỉ đạo", "don_vi_xu_ly": "Đơn vị/người xử lý",
              "han_xu_ly": "Hạn xử lý", "trang_thai": "Trạng thái"} if kind == "den" else
             {"so_di": "Số", "ngay_ban_hanh": "Ngày ban hành", "so_ky_hieu": "Số, ký hiệu", "trich_yeu": "Trích yếu", "nguoi_ky": "Người ký",
              "noi_nhan": "Nơi nhận", "tra_loi_van_ban": "Trả lời văn bản số", "nguoi_phat_hanh": "Người phát hành", "trang_thai": "Trạng thái"})
    df = pd.DataFrame([{v: r.get(k) for k, v in names.items()} for r in rows], columns=list(names.values()))
    title = "so_van_ban_den" if kind == "den" else "so_van_ban_di"
    return xlsx_response({title: df}, f"{title}_{y}.xlsx")
