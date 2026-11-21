/** Các màn hình vận hành của quản trị hệ thống (8 nhóm chức năng) */
import { useEffect, useState } from "react";
import {
  Alert, Badge, Button, Card, Checkbox, Col, DatePicker, Descriptions, Empty, Form, Input, InputNumber, List, Modal, Popconfirm,
  Radio, Row, Select, Space, Statistic, Switch, Table, Tabs, Tag, Typography, Upload, message,
} from "antd";
import {
  CloudDownloadOutlined, CloudUploadOutlined, CopyOutlined, DatabaseOutlined, DeleteOutlined, DownloadOutlined, KeyOutlined,
  LockOutlined, LogoutOutlined, NotificationOutlined, PlusOutlined, ReloadOutlined, SendOutlined, WarningOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { api, download } from "../api";

const SEV: Record<string, [string, string]> = { cao: ["red", "Cao"], trung_binh: ["orange", "Trung bình"], thap: ["blue", "Thấp"] };
const fmtBytes = (n: number) => n > 1e9 ? `${(n / 1e9).toFixed(2)} GB` : n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${(n / 1e3).toFixed(0)} KB`;
const fmtUA = (ua?: string) => !ua ? "—" : /Edg/.test(ua) ? "Edge" : /Chrome/.test(ua) ? "Chrome" : /Firefox/.test(ua) ? "Firefox" : /python|urllib/i.test(ua) ? "Ứng dụng/API" : ua.slice(0, 30);

// ============================================================ 1. phiên đăng nhập

export function SessionsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [all, setAll] = useState(false);
  const load = () => api.get("/admin/sessions", { params: { active_only: !all } }).then((r) => setRows(r.data));
  useEffect(() => { load(); }, [all]);
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Switch checked={all} onChange={setAll} /> <span>Hiện cả phiên đã kết thúc</span>
        <Button icon={<ReloadOutlined />} onClick={load}>Làm mới</Button>
        <span className="muted">{rows.filter((r) => r.online).length} người đang trực tuyến (hoạt động trong 5 phút)</span>
      </Space>
      <Table size="small" rowKey="id" dataSource={rows} pagination={{ pageSize: 15 }} columns={[
        { title: "Người dùng", dataIndex: "username", render: (v, s: any) => <div><b>{v}</b> {s.online && <Badge status="success" text="trực tuyến" />}
          <div className="muted" style={{ fontSize: 12 }}>{s.full_name} · {s.role}</div></div> },
        { title: "Thiết bị / IP", key: "d", render: (_, s: any) => <div>{fmtUA(s.user_agent)}<div className="muted" style={{ fontSize: 12 }}>{s.ip}</div></div> },
        { title: "Đăng nhập lúc", dataIndex: "created_at", render: (v) => dayjs(v).format("HH:mm DD/MM") },
        { title: "Hoạt động gần nhất", dataIndex: "last_seen", render: (v) => dayjs(v).format("HH:mm DD/MM") },
        { title: "Ghi chú", key: "n", render: (_, s: any) => s.impersonated_by ? <Tag color="orange">Xem thử bởi {s.impersonated_by}</Tag>
          : s.revoked ? <Tag>{s.revoked_reason}</Tag> : <span className="muted">hết hạn {dayjs(s.expires_at).format("HH:mm DD/MM")}</span> },
        { title: "", key: "a", render: (_, s: any) => !s.revoked && <Popconfirm title={`Buộc ${s.username} đăng xuất phiên này?`}
          onConfirm={() => api.post(`/admin/sessions/${s.id}/revoke`).then(() => { message.success("Đã buộc đăng xuất"); load(); })}>
          <Button size="small" danger icon={<LogoutOutlined />}>Buộc đăng xuất</Button></Popconfirm> },
      ]} />
    </>
  );
}

// ============================================================ 2. nhập / xuất / không hoạt động

export function ImportUsersModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File>();
  const [res, setRes] = useState<any>();
  const [busy, setBusy] = useState(false);
  const run = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    const fd = new FormData(); fd.append("file", file);
    try { const r = await api.post(`/admin/users/import?dry_run=${dry}`, fd); setRes(r.data); if (!dry) { message.success(`Đã tạo ${r.data.created} tài khoản`); onDone(); } }
    finally { setBusy(false); }
  };
  const exportPw = () => {
    const rows = res.rows.filter((r: any) => r.password).map((r: any) => `${r.username},${r.full_name},${r.password}`).join("\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["﻿Tên đăng nhập,Họ tên,Mật khẩu tạm\n" + rows], { type: "text/csv" }));
    a.download = "mat_khau_tam.csv"; a.click();
  };
  return (
    <Modal open width={820} title="Nhập tài khoản hàng loạt từ Excel" onCancel={onClose} footer={null}>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Quy trình: tải file mẫu → điền → Kiểm tra (không ghi dữ liệu) → Tạo tài khoản. Mỗi tài khoản nhận mật khẩu tạm và phải đổi ở lần đăng nhập đầu." />
      <Space wrap style={{ marginBottom: 12 }}>
        <Button icon={<DownloadOutlined />} onClick={() => download("/admin/users/template.xlsx", {}, "mau_nhap_tai_khoan.xlsx")}>Tải file mẫu</Button>
        <Upload beforeUpload={(f) => { setFile(f); setRes(undefined); return false; }} maxCount={1} accept=".xlsx,.xls,.csv" showUploadList={{ showRemoveIcon: false }}>
          <Button icon={<CloudUploadOutlined />}>Chọn file</Button></Upload>
        <Button disabled={!file} loading={busy} onClick={() => run(true)}>Kiểm tra</Button>
        <Button type="primary" disabled={!res || !res.valid || !res.dry_run} loading={busy} onClick={() => run(false)}>Tạo {res?.valid ?? 0} tài khoản hợp lệ</Button>
      </Space>
      {res && <>
        <Alert type={res.dry_run ? (res.valid === res.total ? "success" : "warning") : "success"} showIcon style={{ marginBottom: 8 }}
          message={res.dry_run ? `${res.valid}/${res.total} dòng hợp lệ – dòng lỗi sẽ bị bỏ qua` : `Đã tạo ${res.created} tài khoản`}
          action={!res.dry_run && res.created > 0 && <Button size="small" onClick={exportPw}>Tải danh sách mật khẩu tạm</Button>} />
        <Table size="small" rowKey="row" pagination={{ pageSize: 8 }} dataSource={res.rows} columns={[
          { title: "Dòng", dataIndex: "row", width: 60 }, { title: "Tên đăng nhập", dataIndex: "username" }, { title: "Họ tên", dataIndex: "full_name" },
          { title: "Kết quả", key: "k", render: (_, r: any) => r.ok ? <Tag color="green">Hợp lệ</Tag> : <Tag color="red">Lỗi</Tag> },
          { title: "Chi tiết", dataIndex: "message" },
          ...(!res.dry_run ? [{ title: "Mật khẩu tạm", dataIndex: "password", render: (v: string) => v && <Typography.Text copyable code>{v}</Typography.Text> }] : []),
        ]} />
      </>}
    </Modal>
  );
}

export function InactiveUsersModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [d, setD] = useState<any>();
  const [sel, setSel] = useState<number[]>([]);
  const load = () => api.get("/admin/users/inactive").then((r) => setD(r.data));
  useEffect(() => { load(); }, []);
  return (
    <Modal open width={820} title={`Tài khoản không hoạt động trên ${d?.days ?? ""} ngày`} onCancel={onClose}
      okText={`Khóa ${sel.length} tài khoản`} okButtonProps={{ danger: true, disabled: !sel.length }}
      onOk={() => api.post("/admin/users/bulk-lock", { ids: sel }).then((r) => { message.success(`Đã khóa ${r.data.locked} tài khoản`); setSel([]); load(); onDone(); })}>
      <Typography.Paragraph type="secondary">Tài khoản lâu không dùng là rủi ro bảo mật (có thể đã nghỉ việc nhưng chưa thu hồi). Ngưỡng số ngày chỉnh trong Cấu hình hệ thống.</Typography.Paragraph>
      <Table size="small" rowKey="id" dataSource={d?.items ?? []} pagination={{ pageSize: 10 }}
        rowSelection={{ selectedRowKeys: sel, onChange: (k) => setSel(k as number[]) }} columns={[
          { title: "Tài khoản", dataIndex: "username" }, { title: "Họ tên", dataIndex: "full_name" },
          { title: "Vai trò", dataIndex: ["role", "name"] }, { title: "Đơn vị", dataIndex: ["unit", "name"] },
          { title: "Đăng nhập gần nhất", dataIndex: "last_login", render: (v) => v ? dayjs(v).format("DD/MM/YYYY") : <Tag>Chưa bao giờ</Tag> },
        ]} />
    </Modal>
  );
}

// ============================================================ 3. chuyển giao

export function HandoverModal({ user, onClose, onDone }: { user: any; onClose: () => void; onDone: () => void }) {
  const [d, setD] = useState<any>();
  const [form] = Form.useForm();
  useEffect(() => { api.get(`/admin/users/${user.id}/handover`).then((r) => setD(r.data)); }, []);
  const submit = async () => {
    const v = await form.validateFields();
    const r = await api.post(`/admin/users/${user.id}/handover`, v);
    message.success(`Đã bàn giao ${r.data.tasks} việc${r.data.am_units ? `, ${r.data.am_units} đơn vị AM` : ""}${r.data.locked ? ", đã khóa tài khoản" : ""}`);
    onDone();
  };
  return (
    <Modal open width={720} title={`Chuyển giao công việc – ${user.full_name}`} onCancel={onClose} onOk={submit} okText="Bàn giao">
      {d && <>
        <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Dùng khi cán bộ nghỉ việc, nghỉ dài ngày hoặc chuyển công tác: chuyển các việc đang xử lý sang người thay thế, (tùy chọn) khóa tài khoản và đăng xuất mọi thiết bị." />
        <Descriptions size="small" bordered column={2} items={[
          { label: "Việc đang xử lý", children: <b>{d.tasks.length}</b> }, { label: "Đơn vị AM phụ trách", children: <b>{d.am_units}</b> },
        ]} />
        {d.tasks.length > 0 && <List size="small" style={{ margin: "8px 0", maxHeight: 160, overflow: "auto" }} dataSource={d.tasks}
          renderItem={(t: any) => <List.Item><span>{t.code} – {t.title}</span><span className="muted">hạn {dayjs(t.deadline).format("DD/MM")}</span></List.Item>} />}
        <Form form={form} layout="vertical" initialValues={{ lock_account: true }} style={{ marginTop: 12 }}>
          <Form.Item name="to_user_id" label="Người nhận bàn giao" rules={[{ required: true }]}>
            <Select options={d.candidates.map((c: any) => ({ value: c.id, label: `${c.full_name} (${c.username}) – ${c.role}` }))}
              notFoundContent="Không có người cùng đơn vị – hãy cấp tài khoản cho người thay thế trước" />
          </Form.Item>
          <Form.Item name="note" label="Ghi chú (ghi vào lịch sử xử lý)"><Input placeholder="VD: Chuyển công tác theo Quyết định số…" /></Form.Item>
          <Form.Item name="lock_account" valuePropName="checked"><Checkbox>Khóa tài khoản {user.username} và đăng xuất mọi thiết bị</Checkbox></Form.Item>
        </Form>
      </>}
    </Modal>
  );
}

// ============================================================ 4. cấu hình, kỳ, địa bàn

export function SettingsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [draft, setDraft] = useState<Record<string, any>>({});
  const load = () => api.get("/admin/settings").then((r) => { setRows(r.data); setDraft({}); });
  useEffect(() => { load(); }, []);
  const groups = [...new Set(rows.map((r) => r.group_name))];
  const val = (r: any) => (r.key in draft ? draft[r.key] : r.value);
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" disabled={!Object.keys(draft).length}
          onClick={() => api.put("/admin/settings", draft).then(() => { message.success("Đã lưu cấu hình"); load(); })}>Lưu {Object.keys(draft).length || ""} thay đổi</Button>
        {Object.keys(draft).length > 0 && <Button onClick={() => setDraft({})}>Hủy</Button>}
      </Space>
      <Row gutter={[16, 16]}>
        {groups.map((g) => (
          <Col xs={24} lg={12} key={g}>
            <Card size="small" title={g}>
              {rows.filter((r) => r.group_name === g).map((r) => (
                <div key={r.key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "6px 0", borderBottom: "1px solid #f1f5f9" }}>
                  <div><div>{r.description}</div>
                    <div className="muted" style={{ fontSize: 11 }}>{r.key}{r.updated_by && ` · sửa bởi ${r.updated_by} ${dayjs(r.updated_at).format("DD/MM HH:mm")}`}</div></div>
                  {r.type === "bool" ? <Switch checked={!!val(r)} onChange={(v) => setDraft({ ...draft, [r.key]: v })} />
                    : r.type === "int" ? <InputNumber min={0} value={val(r)} onChange={(v) => setDraft({ ...draft, [r.key]: v })} style={{ width: 110 }} />
                      : <Input value={val(r)} onChange={(e) => setDraft({ ...draft, [r.key]: e.target.value })} style={{ width: 280 }} />}
                </div>
              ))}
            </Card>
          </Col>
        ))}
      </Row>
    </>
  );
}

export function PeriodsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const load = () => api.get("/admin/periods").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const put = (p: any, body: any, msg: string) => api.put(`/admin/periods/${p.id}`, body).then(() => { message.success(msg); load(); });
  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Kỳ hiện hành là kỳ mặc định trên toàn hệ thống. Kỳ đã khóa không nhận dữ liệu mới (file, API, đồng bộ) và không tính lại – giữ nguyên kết quả đã công bố." />
      <Popconfirm title="Tạo kỳ đánh giá kế tiếp?" onConfirm={() => api.post("/admin/periods").then((r) => { message.success(`Đã tạo kỳ ${r.data.code}`); load(); })}>
        <Button icon={<PlusOutlined />} style={{ marginBottom: 12 }}>Tạo kỳ kế tiếp</Button></Popconfirm>
      <Table size="small" rowKey="id" dataSource={rows} pagination={false} columns={[
        { title: "Kỳ", dataIndex: "name", render: (v, p: any) => <Space><b>{v}</b>{p.is_current && <Tag color="blue">Hiện hành</Tag>}{p.is_locked && <Tag icon={<LockOutlined />} color="red">Đã khóa số liệu</Tag>}</Space> },
        { title: "Thời gian", key: "t", render: (_, p: any) => `${dayjs(p.start_date).format("DD/MM/YYYY")} – ${dayjs(p.end_date).format("DD/MM/YYYY")}` },
        { title: "Số liệu đã nhận", dataIndex: "metric_count", align: "right" }, { title: "Đơn vị đã chấm", dataIndex: "unit_count", align: "right" },
        { title: "", key: "a", render: (_, p: any) => <Space>
          {!p.is_current && !p.is_locked && <Button size="small" onClick={() => put(p, { is_current: true }, `Đặt ${p.code} làm kỳ hiện hành`)}>Đặt làm hiện hành</Button>}
          {!p.is_current && <Popconfirm title={p.is_locked ? "Mở khóa số liệu kỳ này?" : "Khóa số liệu kỳ này? Sẽ không nhận dữ liệu mới và không tính lại."}
            onConfirm={() => put(p, { is_locked: !p.is_locked }, p.is_locked ? "Đã mở khóa" : "Đã khóa số liệu")}>
            <Button size="small" danger={!p.is_locked}>{p.is_locked ? "Mở khóa" : "Khóa số liệu"}</Button></Popconfirm>}
        </Space> },
      ]} />
    </>
  );
}

export function RegionsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  const load = () => api.get("/admin/regions").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    const v = await form.validateFields();
    if (edit.id) await api.put(`/admin/regions/${edit.id}`, { ...v, code: edit.code }); else await api.post("/admin/regions", v);
    message.success("Đã lưu địa bàn"); setEdit(null); load();
  };
  const T: Record<string, string> = { tinh: "Tỉnh", phuong: "Phường", xa: "Xã", dac_khu: "Đặc khu" };
  return (
    <>
      <Button icon={<PlusOutlined />} style={{ marginBottom: 12 }} onClick={() => { setEdit({}); form.resetFields(); }}>Thêm xã/phường</Button>
      <Table size="small" rowKey="id" dataSource={rows} pagination={{ pageSize: 15 }} columns={[
        { title: "Mã", dataIndex: "code", width: 80 }, { title: "Tên", dataIndex: "name" }, { title: "Loại", dataIndex: "type", render: (v) => T[v] },
        { title: "Dân số", dataIndex: "population", align: "right", render: (v) => v?.toLocaleString("vi-VN") },
        { title: "Diện tích (km²)", dataIndex: "area_km2", align: "right" }, { title: "Số đơn vị", dataIndex: "unit_count", align: "right" },
        { title: "", key: "a", render: (_, r: any) => r.type !== "tinh" && <Button size="small" onClick={() => { setEdit(r); form.setFieldsValue(r); }}>Sửa</Button> },
      ]} />
      <Modal open={!!edit} title={edit?.id ? `Sửa ${edit.name}` : "Thêm địa bàn"} onOk={save} onCancel={() => setEdit(null)} okText="Lưu">
        <Form form={form} layout="vertical" initialValues={{ type: "xa" }}>
          <Form.Item name="code" label="Mã" rules={[{ required: true }]}><Input disabled={!!edit?.id} /></Form.Item>
          <Form.Item name="name" label="Tên (VD: Xã Tân Biên)" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="type" label="Loại"><Radio.Group options={[{ value: "phuong", label: "Phường" }, { value: "xa", label: "Xã" }, { value: "dac_khu", label: "Đặc khu" }]} /></Form.Item>
          <Space><Form.Item name="population" label="Dân số"><InputNumber min={0} /></Form.Item><Form.Item name="area_km2" label="Diện tích (km²)"><InputNumber min={0} /></Form.Item></Space>
        </Form>
      </Modal>
    </>
  );
}

// ============================================================ 5. thông báo hệ thống

export function AnnouncementsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [form] = Form.useForm();
  const load = () => api.get("/admin/announcements").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const send = async () => {
    const v = await form.validateFields();
    const r = await api.post("/admin/announcements", v);
    message.success(`Đã gửi tới ${r.data.recipients} người dùng`); form.resetFields(); load();
  };
  return (
    <Row gutter={16}>
      <Col xs={24} lg={10}>
        <Card size="small" title={<><NotificationOutlined /> Soạn thông báo</>}>
          <Form form={form} layout="vertical" initialValues={{ target: "all", severity: "info" }}>
            <Form.Item name="title" label="Tiêu đề" rules={[{ required: true }]}><Input placeholder="VD: Bảo trì hệ thống 22h00 ngày 20/11" /></Form.Item>
            <Form.Item name="body" label="Nội dung"><Input.TextArea rows={4} /></Form.Item>
            <Form.Item name="target" label="Gửi tới"><Select options={[{ value: "all", label: "Tất cả người dùng" }, { value: "tinh", label: "Cấp tỉnh" },
              { value: "so", label: "Sở, ngành" }, { value: "xa", label: "Cấp xã, phường" }, { value: "truong", label: "Cơ sở giáo dục" }, { value: "khac", label: "Đối tác (AM)" }]} /></Form.Item>
            <Form.Item name="severity" label="Mức độ"><Radio.Group options={[{ value: "info", label: "Thông tin" }, { value: "warning", label: "Lưu ý" }, { value: "critical", label: "Khẩn" }]} /></Form.Item>
            <Popconfirm title="Gửi thông báo tới người dùng?" onConfirm={send}><Button type="primary" icon={<SendOutlined />}>Gửi thông báo</Button></Popconfirm>
          </Form>
        </Card>
      </Col>
      <Col xs={24} lg={14}>
        <Card size="small" title="Đã gửi">
          <List dataSource={rows} locale={{ emptyText: "Chưa gửi thông báo nào" }} renderItem={(a: any) => (
            <List.Item><List.Item.Meta title={<Space>{a.severity !== "info" && <Tag color={a.severity === "critical" ? "red" : "orange"}>{a.severity === "critical" ? "Khẩn" : "Lưu ý"}</Tag>}{a.title}</Space>}
              description={<>{a.body}<div className="muted" style={{ fontSize: 12 }}>{a.target_name} · {a.recipients} người nhận · {a.created_by} · {dayjs(a.created_at).format("HH:mm DD/MM/YYYY")}</div></>} /></List.Item>)} />
        </Card>
      </Col>
    </Row>
  );
}

// ============================================================ 6. giám sát & sao lưu

export function MonitorTab() {
  const [m, setM] = useState<any>();
  const [bk, setBk] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const load = () => { api.get("/admin/monitor").then((r) => setM(r.data)); api.get("/admin/backups").then((r) => setBk(r.data)); };
  useEffect(() => { load(); }, []);
  const backup = async () => { setBusy(true); try { const r = await api.post("/admin/backups"); message.success(`Đã sao lưu ${r.data.file_name}`); load(); } finally { setBusy(false); } };
  const dl = async (b: any) => {
    const r = await api.get(`/admin/backups/${b.id}/download`, { responseType: "blob" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(r.data); a.download = b.file_name; a.click();
  };
  if (!m) return null;
  const up = m.uptime_seconds;
  return (
    <>
      <Row gutter={[12, 12]}>
        {[["Thời gian chạy", `${Math.floor(up / 3600)} giờ ${Math.floor((up % 3600) / 60)} phút`], ["Dung lượng CSDL", fmtBytes(m.db_size)],
          ["Phiên hoạt động (30')", m.active_sessions], ["Lỗi máy chủ 24h", m.errors_24h], ["Tệp đính kèm", fmtBytes(m.upload_size)],
          ["Bản sao lưu gần nhất", m.last_backup ? dayjs(m.last_backup).format("HH:mm DD/MM") : "Chưa có"]].map(([t, v]) => (
          <Col xs={12} md={8} xl={4} key={t as string}><Card size="small"><Statistic title={t} value={v as any} valueStyle={{ fontSize: 20, color: t === "Lỗi máy chủ 24h" && m.errors_24h ? "#dc2626" : undefined }} /></Card></Col>))}
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 12 }}>
        <Col xs={24} lg={10}><Card size="small" title={<><DatabaseOutlined /> PostgreSQL {m.db_version}</>}>
          <Table size="small" pagination={false} rowKey="schema" dataSource={m.schemas} columns={[
            { title: "Schema", dataIndex: "schema", render: (v) => <Tag color={{ bronze: "orange", silver: "default", gold: "gold" }[v as string] ?? "blue"}>{v}</Tag> },
            { title: "Số bản ghi", dataIndex: "rows", align: "right", render: (v) => v.toLocaleString("vi-VN") }]} />
          <Typography.Title level={5} style={{ marginTop: 12 }}>Bảng lớn nhất</Typography.Title>
          <List size="small" dataSource={m.top_tables.slice(0, 6)} renderItem={(t: any) => <List.Item><span>{t.schema}.{t.table}</span><b>{t.rows.toLocaleString("vi-VN")}</b></List.Item>} />
        </Card></Col>
        <Col xs={24} lg={14}>
          <Card size="small" title="Sao lưu cơ sở dữ liệu" extra={<Button type="primary" icon={<CloudDownloadOutlined />} loading={busy} onClick={backup}>Sao lưu ngay</Button>}>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>Dùng pg_dump (định dạng custom). Phục hồi: <code>pg_restore -c -d dti_platform tệp.dump</code>. Nên tải bản sao lưu lưu trữ ngoài máy chủ.</Typography.Paragraph>
            <Table size="small" rowKey="id" pagination={{ pageSize: 5 }} dataSource={bk} columns={[
              { title: "Tệp", dataIndex: "file_name" }, { title: "Dung lượng", dataIndex: "size", render: (v) => v ? fmtBytes(v) : "—" },
              { title: "Trạng thái", dataIndex: "status", render: (v, b: any) => v === "thanh_cong" ? <Tag color="green">Thành công</Tag> : <Tag color="red" title={b.message}>Lỗi</Tag> },
              { title: "Thời gian", dataIndex: "created_at", render: (v) => dayjs(v).format("HH:mm DD/MM/YY") },
              { title: "", key: "a", render: (_, b: any) => <Space>
                {b.exists && <Button size="small" icon={<DownloadOutlined />} onClick={() => dl(b)} />}
                <Popconfirm title="Xóa bản sao lưu?" onConfirm={() => api.delete(`/admin/backups/${b.id}`).then(load)}><Button size="small" danger icon={<DeleteOutlined />} /></Popconfirm></Space> },
            ]} />
          </Card>
          <Card size="small" title="Lỗi máy chủ gần đây" style={{ marginTop: 12 }}>
            {m.recent_errors.length ? <List size="small" dataSource={m.recent_errors} renderItem={(e: any) => <List.Item>
              <span><Tag color="red">{e.status}</Tag>{e.method} {e.path}<div className="muted" style={{ fontSize: 12 }}>{e.message}</div></span>
              <span className="muted">{dayjs(e.created_at).format("HH:mm DD/MM")}</span></List.Item>} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có lỗi" />}
          </Card>
        </Col>
      </Row>
    </>
  );
}

// ============================================================ 7. nhật ký nâng cao & cảnh báo bảo mật

export function SecurityAlerts({ compact = false }: { compact?: boolean }) {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { api.get("/admin/security-alerts").then((r) => setRows(r.data)); }, []);
  const data = compact ? rows.slice(0, 6) : rows;
  return (
    <Table size="small" rowKey={(r: any) => r.type + r.username + r.at} pagination={compact ? false : { pageSize: 10 }} dataSource={data}
      locale={{ emptyText: "Không phát hiện bất thường" }} columns={[
        { title: "Mức", dataIndex: "severity", width: 100, render: (v) => <Tag color={SEV[v][0]}>{SEV[v][1]}</Tag> },
        { title: "Loại", dataIndex: "type", render: (v) => <span><WarningOutlined style={{ color: "#ea580c" }} /> {v}</span> },
        { title: "Tài khoản", dataIndex: "username", width: 140 },
        ...(!compact ? [{ title: "Chi tiết", dataIndex: "detail" }] : []),
        { title: "Thời điểm", dataIndex: "at", width: 120, render: (v) => v && dayjs(v).format("HH:mm DD/MM") },
      ]} />
  );
}

export function AuditTab() {
  const [data, setData] = useState<any>({ items: [], total: 0, actions: [] });
  const [f, setF] = useState<any>({ page: 1, size: 20 });
  useEffect(() => { api.get("/admin/audit", { params: f }).then((r) => setData(r.data)); }, [f]);
  const params = { ...f, page: undefined, size: undefined };
  return (
    <Tabs items={[
      { key: "log", label: "Nhật ký hoạt động", children: <>
        <Space style={{ marginBottom: 12 }} wrap>
          <Input.Search allowClear placeholder="Người dùng" style={{ width: 170 }} onSearch={(username) => setF({ ...f, username, page: 1 })} />
          <Select allowClear showSearch placeholder="Hành động" style={{ width: 190 }} onChange={(action) => setF({ ...f, action, page: 1 })}
            options={data.actions.map((v: string) => ({ value: v, label: v }))} />
          <DatePicker.RangePicker format="DD/MM/YYYY" onChange={(v) => setF({ ...f, page: 1, date_from: v?.[0]?.format("YYYY-MM-DD"), date_to: v?.[1]?.format("YYYY-MM-DD") })} />
          <Button icon={<DownloadOutlined />} onClick={() => download("/admin/audit/export.xlsx", params, `nhat_ky_${dayjs().format("YYYYMMDD")}.xlsx`)}>Xuất Excel</Button>
        </Space>
        <Table size="small" rowKey="id" dataSource={data.items} pagination={{ current: f.page, pageSize: f.size, total: data.total, showTotal: (t) => `${t} bản ghi`, onChange: (page, size) => setF({ ...f, page, size }) }} columns={[
          { title: "Thời gian", dataIndex: "created_at", width: 150, render: (v) => dayjs(v).format("HH:mm:ss DD/MM/YY") },
          { title: "Người dùng", dataIndex: "username", width: 150 },
          { title: "Hành động", dataIndex: "action", width: 140, render: (v) => <Tag color={v.includes("failed") ? "red" : v.startsWith("impersonate") ? "orange" : undefined}>{v}</Tag> },
          { title: "Đối tượng", key: "e", width: 160, render: (_, a: any) => a.entity && `${a.entity} #${a.entity_id ?? ""}` },
          { title: "Chi tiết", dataIndex: "detail", render: (v) => v && <code style={{ fontSize: 11 }}>{JSON.stringify(v).slice(0, 140)}</code> },
          { title: "IP", dataIndex: "ip", width: 120 },
        ]} />
      </> },
      { key: "sec", label: "Cảnh báo bảo mật", children: <SecurityAlerts /> },
    ]} />
  );
}

// ============================================================ 8. khóa API tích hợp

export function ApiKeysTab() {
  const [d, setD] = useState<any>({ items: [], scopes: {} });
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<string>();
  const [form] = Form.useForm();
  const load = () => api.get("/admin/api-keys").then((r) => setD(r.data));
  useEffect(() => { load(); }, []);
  const create = async () => {
    const v = await form.validateFields();
    const r = await api.post("/admin/api-keys", v);
    setCreated(r.data.key); setOpen(false); form.resetFields(); load();
  };
  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Cấp khóa cho hệ thống khác (trục LGSP tỉnh, VBĐH…) gọi API tích hợp. Hệ thống chỉ lưu bản băm – khóa gốc hiển thị một lần khi tạo."
        description={<>Gọi API: header <code>X-API-Key: dti_…</code> · <code>GET /api/integration/dti?period=2026-Q4</code> · <code>GET /api/integration/units</code> · <code>POST /api/integration/metrics</code></>} />
      <Button type="primary" icon={<KeyOutlined />} style={{ marginBottom: 12 }} onClick={() => setOpen(true)}>Tạo khóa API</Button>
      {created && <Alert type="success" showIcon closable onClose={() => setCreated(undefined)} style={{ marginBottom: 12 }} message="Khóa API mới – sao chép ngay, sẽ không hiển thị lại"
        description={<Typography.Text copyable={{ icon: <CopyOutlined /> }} code style={{ fontSize: 14 }}>{created}</Typography.Text>} />}
      <Table size="small" rowKey="id" dataSource={d.items} pagination={false} columns={[
        { title: "Tên hệ thống", dataIndex: "name", render: (v, k: any) => <div><b>{v}</b><div className="muted" style={{ fontSize: 12 }}><code>{k.prefix}…</code></div></div> },
        { title: "Phạm vi quyền", dataIndex: "scopes", render: (v: string[]) => v.map((s) => <Tag key={s} title={d.scopes[s]}>{s}</Tag>) },
        { title: "Hết hạn", dataIndex: "expires_at", render: (v) => v ? dayjs(v).format("DD/MM/YYYY") : "Không" },
        { title: "Sử dụng", key: "u", render: (_, k: any) => <div>{k.use_count} lần<div className="muted" style={{ fontSize: 12 }}>{k.last_used_at ? dayjs(k.last_used_at).format("HH:mm DD/MM") : "chưa dùng"}</div></div> },
        { title: "Trạng thái", dataIndex: "revoked", render: (v) => v ? <Tag color="red">Đã thu hồi</Tag> : <Tag color="green">Hiệu lực</Tag> },
        { title: "", key: "a", render: (_, k: any) => !k.revoked && <Popconfirm title="Thu hồi khóa? Hệ thống đang dùng khóa này sẽ mất kết nối ngay."
          onConfirm={() => api.post(`/admin/api-keys/${k.id}/revoke`).then(load)}><Button size="small" danger>Thu hồi</Button></Popconfirm> },
      ]} />
      <Modal open={open} title="Tạo khóa API" onOk={create} onCancel={() => setOpen(false)} okText="Tạo khóa">
        <Form form={form} layout="vertical" initialValues={{ scopes: ["dti.read"], expires_days: 365 }}>
          <Form.Item name="name" label="Tên hệ thống sử dụng" rules={[{ required: true }]}><Input placeholder="VD: Trục LGSP của tỉnh" /></Form.Item>
          <Form.Item name="scopes" label="Phạm vi quyền" rules={[{ required: true }]}>
            <Checkbox.Group options={Object.entries(d.scopes).map(([value, label]) => ({ value, label: `${value} – ${label}` }))} style={{ display: "grid", gap: 4 }} /></Form.Item>
          <Form.Item name="expires_days" label="Hiệu lực (ngày, 0 = không hết hạn)"><InputNumber min={0} /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}
