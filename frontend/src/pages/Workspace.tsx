import { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Empty, List, Row, Space, Statistic, Tag, Typography } from "antd";
import {
  AimOutlined, AuditOutlined, BarChartOutlined, BookOutlined, BulbOutlined, CloudUploadOutlined, FileExcelOutlined, InboxOutlined, ProfileOutlined,
  SafetyCertificateOutlined, ScheduleOutlined, TeamOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { Delta, LevelTag, Score } from "../components/common";
import { ActionModal, TaskDetail } from "./Tasks";
import { SecurityAlerts } from "./AdminOps";

const ACTION_LABEL: Record<string, string> = {
  tiep_nhan: "Tiếp nhận", phan_cong: "Phân công", trinh: "Trình", kiem_tra: "Kiểm tra", ky_duyet: "Ký duyệt", bao_cao: "Ký duyệt",
  phat_hanh: "Phát hành", xac_nhan: "Xác nhận", assess_prepare: "Khai phiếu", assess_submit: "Duyệt & nộp", assess_review: "Thẩm định", assess_publish: "Mở",
};

/** Lối tắt riêng cho từng chức danh – chỉ hiện chức năng người đó được dùng */
const SHORTCUTS: { perm: string; label: string; to: string; icon: JSX.Element; desc: string }[] = [
  { perm: "dashboard.view", label: "Tổng quan CĐS", to: "/dashboard", icon: <BarChartOutlined />, desc: "Chỉ số DTI, xu hướng, xếp hạng" },
  { perm: "data.import", label: "Nhập dữ liệu", to: "/data", icon: <CloudUploadOutlined />, desc: "Tải file khảo sát, pipeline Bronze→Gold" },
  { perm: "criteria.manage", label: "Bộ tiêu chí", to: "/framework", icon: <ProfileOutlined />, desc: "Trọng số, mục tiêu DTI" },
  { perm: "plan.view", label: "Đề xuất & hoạch định", to: "/planning", icon: <BulbOutlined />, desc: "Nhóm giải pháp ưu tiên" },
  { perm: "am.view", label: "AM Intelligence", to: "/am", icon: <AimOutlined />, desc: "Cơ hội dịch vụ, gia hạn" },
  { perm: "report.export", label: "Xuất báo cáo", to: "/reports", icon: <FileExcelOutlined />, desc: "Báo cáo Excel theo phạm vi" },
  { perm: "user.manage", label: "Quản trị tài khoản", to: "/admin/users", icon: <SafetyCertificateOutlined />, desc: "Cấp, khóa tài khoản, gán vai trò" },
  { perm: "role.manage", label: "Xem dưới vai trò", to: "/roles", icon: <TeamOutlined />, desc: "Hỗ trợ người dùng: xem đúng giao diện của họ" },
  { perm: "task.assign", label: "Giao nhiệm vụ", to: "/tasks", icon: <ScheduleOutlined />, desc: "Phát hành văn bản giao việc" },
  { perm: "task.receive", label: "Sổ văn bản", to: "/registers", icon: <BookOutlined />, desc: "Sổ văn bản đến, sổ văn bản đi" },
  { perm: "assess.prepare", label: "Tự đánh giá CĐS", to: "/assessment", icon: <AuditOutlined />, desc: "Khai phiếu tự đánh giá kèm minh chứng" },
  { perm: "assess.submit", label: "Tự đánh giá CĐS", to: "/assessment", icon: <AuditOutlined />, desc: "Duyệt, nộp phiếu của đơn vị" },
  { perm: "assess.review", label: "Thẩm định đánh giá", to: "/assessments", icon: <AuditOutlined />, desc: "Thẩm định phiếu tự đánh giá" },
  { perm: "assess.publish", label: "Công bố kết quả", to: "/assessments", icon: <AuditOutlined />, desc: "Công bố kết quả chính thức của kỳ" },
];

/** Bàn làm việc của quản trị: tình hình vận hành hệ thống (không có số liệu nghiệp vụ) */
function AdminPanel() {
  const { can } = useAuth();
  const [s, setS] = useState<any>();
  const [logs, setLogs] = useState<any[]>([]);
  useEffect(() => {
    api.get("/admin/stats").then((r) => setS(r.data));
    if (can("audit.view")) api.get("/admin/audit-logs", { params: { size: 8 } }).then((r) => setLogs(r.data.items));
  }, []);
  if (!s) return null;
  return (
    <Row gutter={[16, 16]}>
      {[["Tài khoản", s.users, "#1d4ed8"], ["Đang hoạt động", s.active_users, "#16a34a"], ["Đã khóa", s.locked_users, "#dc2626"],
        ["Chưa từng đăng nhập", s.never_login, "#ea580c"], ["Đơn vị trong danh mục", s.units, "#475569"], ["Đăng nhập 7 ngày", s.logins_7d, "#7c3aed"]].map(([t, v, c]) => (
        <Col xs={12} md={8} xl={4} key={t as string}><Card size="small"><Statistic title={t} value={v as number} valueStyle={{ color: c as string }} /></Card></Col>))}
      <Col xs={24} lg={10}><Card size="small" title="Tài khoản theo cấp">
        <List size="small" dataSource={s.by_level} renderItem={(x: any) => <List.Item><span>{x.level}</span><b>{x.count}</b></List.Item>} />
      </Card></Col>
      <Col xs={24} lg={14}><Card size="small" title="Hoạt động gần đây">
        <List size="small" dataSource={logs} renderItem={(l: any) => <List.Item>
          <span><Tag>{l.action}</Tag>{l.username} {l.entity && <span className="muted">· {l.entity} #{l.entity_id}</span>}</span>
          <span className="muted" style={{ fontSize: 12 }}>{dayjs(l.created_at).format("HH:mm DD/MM")}</span></List.Item>} />
      </Card></Col>
    </Row>
  );
}

export default function Workspace() {
  const { user, can } = useAuth();
  const nav = useNavigate();
  const [w, setW] = useState<any>();
  const [act, setAct] = useState<{ a: any; action: string } | null>(null);
  const [detail, setDetail] = useState<number | null>(null);
  const load = () => api.get("/workspace").then((r) => setW(r.data));
  useEffect(() => { load(); }, []);
  const hour = new Date().getHours();
  const greet = hour < 11 ? "Chào buổi sáng" : hour < 14 ? "Chào buổi trưa" : hour < 18 ? "Chào buổi chiều" : "Chào buổi tối";
  const shortcuts = SHORTCUTS.filter((s) => can(s.perm)).filter((s, i, arr) => arr.findIndex((x) => x.to === s.to) === i);
  const openItem = (q: any, it: any) => {
    if (q.kind === "assessment") nav(q.key === "assess_review" ? `/assessments?id=${it.assessment_id}` : q.key === "assess_publish" ? "/assessments" : "/assessment");
    else setAct({ a: { ...it, id: it.assignment_id }, action: q.action });
  };
  const queues = (w?.queues ?? []) as any[];

  return (
    <>
      <Card style={{ marginBottom: 16, background: "linear-gradient(120deg,#0b1f44,#1d4ed8)", border: 0 }} styles={{ body: { padding: 20 } }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <div style={{ color: "#93c5fd", fontSize: 13 }}>{greet}, {dayjs().format("dddd, DD/MM/YYYY")}</div>
            <Typography.Title level={3} style={{ color: "#fff", margin: "4px 0" }}>{user?.full_name}</Typography.Title>
            <Space wrap>
              <Tag color="blue">{user?.role.name}</Tag>
              {user?.unit && <Tag>{user.unit.name}</Tag>}
              {user?.position && <span style={{ color: "#cbd5e1", fontSize: 13 }}>{user.position}</span>}
            </Space>
          </Col>
          {w && queues.length > 0 && <Col><Statistic title={<span style={{ color: "#cbd5e1" }}>Việc cần xử lý</span>} value={w.total_pending} valueStyle={{ color: "#fff", fontWeight: 700 }} /></Col>}
          {w?.unit?.dti != null && can("dashboard.view") && (
            <Col><Card size="small" style={{ minWidth: 170 }}>
              <div className="muted" style={{ fontSize: 12 }}>DTI đơn vị (kỳ hiện hành)</div>
              <Space><Score v={w.unit.dti} size={24} /><LevelTag level={w.unit.level} /></Space>
              <div style={{ fontSize: 12 }}>Hạng {w.unit.rank} · <Delta v={w.unit.delta} /></div>
            </Card></Col>
          )}
        </Row>
      </Card>

      {queues.length > 0 ? (
        <Row gutter={[16, 16]}>
          {queues.map((q) => (
            <Col xs={24} lg={queues.length >= 3 ? 8 : 12} key={q.key}>
              <Card size="small" style={{ height: "100%", borderTop: `3px solid ${q.color}` }}
                title={<Space><Badge count={q.items.length} showZero color={q.items.length ? q.color : "#cbd5e1"} />{q.title}</Space>}>
                <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>{q.hint}</Typography.Paragraph>
                {q.items.length ? (
                  <List size="small" dataSource={q.items.slice(0, 8)} renderItem={(it: any) => (
                    <List.Item style={{ paddingInline: 0 }} actions={[
                      q.action && <Button key="a" size="small" type="primary" style={{ background: q.color }}
                        onClick={() => openItem(q, it)}>{ACTION_LABEL[q.action]}</Button>,
                      q.kind !== "assessment" && <Button key="d" size="small" onClick={() => setDetail(it.task_id)}>Mở</Button>,
                    ].filter(Boolean)}>
                      <List.Item.Meta
                        title={<span style={{ fontSize: 13 }}>{it.is_cascaded && <Tag color="purple">Giao tiếp</Tag>}{it.priority === "khan" && <Tag color="red">Khẩn</Tag>}{it.title}</span>}
                        description={q.kind === "assessment" ? <span style={{ fontSize: 12 }}>
                          {it.unit_name} · <b>{it.status_name}</b>{it.self_score != null && <> · tự chấm ~{it.self_score}</>}
                          {it.review_note && it.status === "tra_lai" && <div style={{ color: "#dc2626" }}>↩ {it.review_note}</div>}
                        </span> : <span style={{ fontSize: 12 }}>
                          {it.code} · {q.key === "confirm" || q.key === "overdue" ? it.unit_name : it.assigner}
                          {" · "}<span style={{ color: it.overdue ? "#dc2626" : it.days_left <= 3 ? "#ea580c" : undefined }}>
                            {it.overdue ? `quá hạn ${-it.days_left} ngày` : `hạn ${dayjs(it.deadline).format("DD/MM")} (còn ${it.days_left} ngày)`}</span>
                          {it.report_doc_number && q.key === "confirm" && <> · BC {it.report_doc_number}</>}
                          {it.return_reason && q.key === "returned" && <div style={{ color: "#dc2626" }}>↩ {it.return_reason}</div>}
                        </span>} />
                    </List.Item>
                  )} />
                ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có việc tồn" />}
                {q.items.length > 8 && <Button type="link" onClick={() => nav("/tasks")}>Xem tất cả {q.items.length} →</Button>}
              </Card>
            </Col>
          ))}
        </Row>
      ) : w && (can("user.manage") ? <AdminPanel /> : (
        <Card size="small" style={{ marginBottom: 16 }}><Empty image={<InboxOutlined style={{ fontSize: 48, color: "#94a3b8" }} />}
          description="Vai trò của bạn không xử lý văn bản, nhiệm vụ – dùng các chức năng bên dưới" /></Card>
      ))}

      {shortcuts.length > 0 && (
        <Card size="small" title="Chức năng của bạn" style={{ marginTop: 16 }}>
          <Row gutter={[12, 12]}>
            {shortcuts.map((s) => (
              <Col xs={12} md={8} xl={6} key={s.to + s.label}>
                <Card size="small" hoverable onClick={() => nav(s.to)}>
                  <Space align="start"><span style={{ fontSize: 22, color: "#1d4ed8" }}>{s.icon}</span>
                    <div><b>{s.label}</b><div className="muted" style={{ fontSize: 12 }}>{s.desc}</div></div></Space>
                </Card>
              </Col>
            ))}
            <Col xs={12} md={8} xl={6}>
              <Card size="small" hoverable onClick={() => nav("/account")}>
                <Space align="start"><span style={{ fontSize: 22, color: "#64748b" }}><TeamOutlined /></span>
                  <div><b>Tài khoản của tôi</b><div className="muted" style={{ fontSize: 12 }}>Thông tin, vai trò, đổi mật khẩu</div></div></Space>
              </Card>
            </Col>
          </Row>
        </Card>
      )}

      {act && <ActionModal a={act.a} action={act.action} onClose={() => setAct(null)} onDone={() => { setAct(null); load(); }} />}
      {detail && <TaskDetail id={detail} onClose={() => { setDetail(null); load(); }} onChanged={load} />}
    </>
  );
}
