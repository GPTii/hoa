import { useEffect, useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import {
  Alert, Badge, Button, Card, Checkbox, Col, Empty, Form, Input, InputNumber, List, Modal, Popconfirm, Row, Select, Space, Statistic,
  Steps, Table, Tabs, Tag, Typography, message,
} from "antd";
import { DeleteOutlined, EyeOutlined, KeyOutlined, LockOutlined, PlusOutlined, SafetyCertificateOutlined, UnlockOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/common";
import AdminSetup, { CatalogImportCard } from "./AdminSetup";
import {
  AnnouncementsTab, ApiKeysTab, AuditTab, HandoverModal, ImportUsersModal, InactiveUsersModal, MonitorTab, PeriodsTab, RegionsTab,
  SecurityAlerts, SessionsTab, SettingsTab,
} from "./AdminOps";
import { DownloadOutlined, LogoutOutlined, SwapOutlined, UploadOutlined, UserDeleteOutlined } from "@ant-design/icons";
import { download } from "../api";

const LEVEL_COLOR: Record<string, string> = { he_thong: "default", tinh: "red", so: "purple", xa: "blue", truong: "green", khac: "gold" };
const SCOPE: Record<string, string> = { all: "Toàn tỉnh", giao_duc: "Toàn ngành giáo dục", region: "Theo xã/phường", unit: "Chỉ đơn vị mình", assigned: "Đơn vị được phân công (AM)" };

type Ctx = { is_super: boolean; scope: string; roles: any[]; units: any[]; levels: { value: string; label: string }[] };

/** Đơn vị hợp lệ cho từng cấp vai trò – tránh gán sai (vd hiệu trưởng cho UBND xã) */
function unitsForLevel(units: any[], level?: string) {
  if (!level) return units;
  if (level === "tinh") return units.filter((u) => ["ubnd_tinh", "van_phong"].includes(u.category));
  if (level === "so") return units.filter((u) => u.category === "so_nganh");
  if (level === "xa") return units.filter((u) => u.category === "ubnd_xa");
  if (level === "truong") return units.filter((u) => u.unit_type === "giao_duc");
  return units;
}

function UserForm({ ctx, edit, onClose, onDone }: { ctx: Ctx; edit: any; onClose: () => void; onDone: () => void }) {
  const [form] = Form.useForm();
  const isNew = !edit.id;
  const [level, setLevel] = useState<string | undefined>(edit.role?.level);
  const roleId = Form.useWatch("role_id", form);
  const levels = ctx.levels.filter((l) => ctx.roles.some((r) => r.level === l.value));
  const roles = ctx.roles.filter((r) => !level || r.level === level);
  const role = ctx.roles.find((r) => r.id === roleId);
  const units = unitsForLevel(ctx.units, level);
  useEffect(() => {
    if (!isNew) form.setFieldsValue({ ...edit, role_id: edit.role.id, unit_id: edit.unit?.id, password: "" });
  }, []);
  const save = async () => {
    const v = await form.validateFields();
    if (isNew) await api.post("/admin/users", v);
    else await api.put(`/admin/users/${edit.id}`, { ...v, username: edit.username });
    message.success(isNew ? "Đã cấp tài khoản" : "Đã cập nhật");
    onDone();
  };
  return (
    <Modal open width={640} title={isNew ? "Cấp tài khoản mới" : `Sửa tài khoản ${edit.username}`} onOk={save} onCancel={onClose} okText="Lưu">
      <Steps size="small" style={{ marginBottom: 16 }} current={!level ? 0 : !roleId ? 1 : 2}
        items={[{ title: "Chọn cấp" }, { title: "Chọn chức danh" }, { title: "Đơn vị & thông tin" }]} />
      <Form form={form} layout="vertical">
        <Row gutter={12}>
          <Col span={10}><Form.Item label="Cấp">
            <Select value={level} onChange={(v) => { setLevel(v); form.setFieldsValue({ role_id: undefined, unit_id: undefined }); }}
              options={levels} placeholder="Tỉnh / Sở / Xã / Trường" />
          </Form.Item></Col>
          <Col span={14}><Form.Item name="role_id" label="Chức danh / vai trò" rules={[{ required: true }]}>
            <Select options={roles.map((r) => ({ value: r.id, label: r.name }))} placeholder="Chọn sau khi chọn cấp" disabled={!level} />
          </Form.Item></Col>
        </Row>
        {role && <Alert style={{ marginBottom: 12 }} type="info" showIcon message={`Phạm vi dữ liệu: ${role.scope_name}`} />}
        <Form.Item name="unit_id" label="Đơn vị công tác" rules={[{ required: role && !["all", "assigned"].includes(role.data_scope) }]}>
          <Select allowClear showSearch optionFilterProp="label" disabled={!level}
            options={units.map((u) => ({ value: u.id, label: `${u.name}${u.category === "ubnd_xa" || u.unit_type === "giao_duc" ? "" : ""}` }))} />
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}>{isNew ? <Form.Item name="username" label="Tên đăng nhập" rules={[{ required: true, pattern: /^[a-z0-9._]{3,40}$/, message: "3–40 ký tự a-z, 0-9, dấu chấm" }]}><Input /></Form.Item>
            : <Form.Item label="Tên đăng nhập"><Input value={edit.username} disabled /></Form.Item>}</Col>
          <Col span={12}><Form.Item name="password" label={isNew ? "Mật khẩu ban đầu" : "Mật khẩu mới (bỏ trống nếu giữ)"} rules={isNew ? [{ required: true, min: 6 }] : []}><Input.Password /></Form.Item></Col>
          <Col span={12}><Form.Item name="full_name" label="Họ tên" rules={[{ required: true }]}><Input /></Form.Item></Col>
          <Col span={12}><Form.Item name="position" label="Chức vụ"><Input placeholder="VD: Văn thư, Phó Chủ tịch…" /></Form.Item></Col>
          <Col span={12}><Form.Item name="email" label="Email"><Input /></Form.Item></Col>
          <Col span={12}><Form.Item name="phone" label="Điện thoại"><Input /></Form.Item></Col>
        </Row>
      </Form>
    </Modal>
  );
}

function AmUnits({ u, ctx, onClose }: { u: any; ctx: Ctx; onClose: () => void }) {
  const [ids, setIds] = useState<number[]>([]);
  useEffect(() => { api.get(`/admin/users/${u.id}/am-units`).then((r) => setIds(r.data)); }, []);
  const regions = [...new Set(ctx.units.map((x) => x.region))];
  const save = async () => { await api.put(`/admin/users/${u.id}/am-units`, ids); message.success(`Đã phân công ${ids.length} đơn vị`); onClose(); };
  return (
    <Modal open width={720} title={`Đơn vị phụ trách – ${u.full_name}`} onOk={save} onCancel={onClose} okText="Lưu phân công">
      <Typography.Paragraph type="secondary">AM chỉ xem được dữ liệu, cơ hội dịch vụ của các đơn vị được phân công.</Typography.Paragraph>
      <Space style={{ marginBottom: 8 }} wrap>
        <span>Thêm nhanh theo địa bàn:</span>
        <Select style={{ width: 240 }} placeholder="Chọn xã/phường" showSearch options={regions.map((r) => ({ value: r, label: r }))}
          onChange={(r) => setIds([...new Set([...ids, ...ctx.units.filter((x) => x.region === r).map((x) => x.id)])])} />
        <Button onClick={() => setIds([])}>Bỏ chọn hết</Button>
      </Space>
      <Select mode="multiple" style={{ width: "100%" }} value={ids} onChange={setIds} showSearch optionFilterProp="label" maxTagCount={12}
        options={ctx.units.map((x) => ({ value: x.id, label: `${x.name} (${x.region})` }))} />
      <div className="muted" style={{ marginTop: 6 }}>Đã chọn {ids.length} đơn vị</div>
    </Modal>
  );
}

function Users({ ctx }: { ctx: Ctx }) {
  const { user, impersonate } = useAuth();
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [f, setF] = useState<any>({ page: 1, size: 15 });
  const [edit, setEdit] = useState<any>(null);
  const [am, setAm] = useState<any>(null);
  const [importing, setImporting] = useState(false);
  const [inactive, setInactive] = useState(false);
  const [handover, setHandover] = useState<any>(null);
  const load = () => api.get("/admin/users", { params: f }).then((r) => setData(r.data));
  useEffect(() => { load(); }, [f]);
  const reset = async (u: any) => {
    const r = await api.post(`/admin/users/${u.id}/reset-password`);
    Modal.success({ title: `Mật khẩu tạm cho ${u.username}`, content: <div>Gửi mật khẩu này cho người dùng (chỉ hiển thị một lần):
      <Typography.Paragraph copyable style={{ fontSize: 20, fontWeight: 700, marginTop: 8 }}>{r.data.temporary_password}</Typography.Paragraph></div> });
  };
  return (
    <>
      <Space style={{ marginBottom: 12 }} wrap>
        <Input.Search allowClear placeholder="Tên đăng nhập, họ tên" style={{ width: 220 }} onSearch={(q) => setF({ ...f, q, page: 1 })} />
        <Select allowClear placeholder="Cấp" style={{ width: 150 }} onChange={(v) => setF({ ...f, level: v, page: 1 })} options={ctx.levels} />
        <Select allowClear placeholder="Vai trò" style={{ width: 230 }} onChange={(v) => setF({ ...f, role_id: v, page: 1 })} options={ctx.roles.map((r) => ({ value: r.id, label: r.name }))} />
        <Select allowClear showSearch optionFilterProp="label" placeholder="Đơn vị" style={{ width: 240 }} onChange={(v) => setF({ ...f, unit_id: v, page: 1 })}
          options={ctx.units.map((u) => ({ value: u.id, label: u.name }))} />
        <Select allowClear placeholder="Trạng thái" style={{ width: 130 }} onChange={(v) => setF({ ...f, active: v, page: 1 })}
          options={[{ value: true, label: "Hoạt động" }, { value: false, label: "Đã khóa" }]} />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setEdit({})}>Cấp tài khoản</Button>
        <Button icon={<UploadOutlined />} onClick={() => setImporting(true)}>Nhập từ Excel</Button>
        <Button icon={<DownloadOutlined />} onClick={() => download("/admin/users/export.xlsx", {}, `tai_khoan_${dayjs().format("YYYYMMDD")}.xlsx`)}>Xuất Excel</Button>
        <Button icon={<UserDeleteOutlined />} onClick={() => setInactive(true)}>Không hoạt động</Button>
      </Space>
      <Table size="small" rowKey="id" dataSource={data.items} scroll={{ x: 1450 }}
        pagination={{ current: f.page, pageSize: f.size, total: data.total, showTotal: (t) => `${t} tài khoản`, onChange: (page, size) => setF({ ...f, page, size }) }}
        columns={[
          { title: "Tài khoản", dataIndex: "username", width: 170, render: (v, u: any) => <div><b>{v}</b><div className="muted" style={{ fontSize: 12 }}>{u.full_name}</div></div> },
          { title: "Cấp", dataIndex: "level_name", width: 130, render: (v, u: any) => <Tag color={LEVEL_COLOR[u.role.level]}>{v}</Tag> },
          { title: "Chức danh / vai trò", dataIndex: ["role", "name"], width: 220, render: (v, u: any) => <div>{v}<div className="muted" style={{ fontSize: 12 }}>{u.position}</div></div> },
          { title: "Đơn vị", dataIndex: ["unit", "name"], width: 230, render: (v, u: any) => v ? <div>{v}<div className="muted" style={{ fontSize: 12 }}>{u.unit_region}</div></div> : <span className="muted">—</span> },
          { title: "Trạng thái", dataIndex: "is_active", width: 130, render: (v, u: any) => <Space direction="vertical" size={0}>
            <Badge status={v ? "success" : "error"} text={v ? "Hoạt động" : "Đã khóa"} />
            {u.locked_until && dayjs(u.locked_until).isAfter(dayjs()) && <Tag color="orange" style={{ fontSize: 11 }}>Khóa tạm đến {dayjs(u.locked_until).format("HH:mm")}</Tag>}</Space> },
          { title: "Đăng nhập gần nhất", dataIndex: "last_login", width: 140, render: (v) => v ? dayjs(v).format("HH:mm DD/MM/YY") : <span className="muted">Chưa đăng nhập</span> },
          { title: "", key: "a", width: 330, fixed: "right", render: (_, u: any) => !u.manageable ? <Tag>Ngoài phạm vi</Tag> : <Space size={4} wrap>
            <Button size="small" onClick={() => setEdit(u)}>Sửa</Button>
            {u.locked_until && dayjs(u.locked_until).isAfter(dayjs()) && <Button size="small" type="primary" ghost onClick={() => api.post(`/admin/users/${u.id}/unlock`).then(() => { message.success("Đã mở khóa đăng nhập"); load(); })}>Mở khóa đăng nhập</Button>}
            {u.id !== user?.id && <Popconfirm title="Buộc tài khoản này đăng xuất khỏi mọi thiết bị?" onConfirm={() => api.post(`/admin/users/${u.id}/revoke-sessions`).then((r) => message.success(`Đã thu hồi ${r.data.revoked} phiên`))}>
              <Button size="small" icon={<LogoutOutlined />} title="Buộc đăng xuất" /></Popconfirm>}
            {u.id !== user?.id && u.is_active && <Button size="small" icon={<SwapOutlined />} title="Chuyển giao công việc" onClick={() => setHandover(u)} />}
            {u.role.code === "am" && ctx.is_super && <Button size="small" onClick={() => setAm(u)}>Đơn vị</Button>}
            {ctx.is_super && u.id !== user?.id && u.is_active && <Button size="small" icon={<EyeOutlined />} title="Xem dưới vai trò (chỉ xem)" onClick={() => impersonate(u.id)} />}
            <Popconfirm title="Cấp lại mật khẩu tạm cho tài khoản này?" onConfirm={() => reset(u)}><Button size="small" icon={<KeyOutlined />} /></Popconfirm>
            {u.id !== user?.id && <Popconfirm title={u.is_active ? "Khóa tài khoản? Người dùng sẽ không đăng nhập được." : "Mở khóa tài khoản?"}
              onConfirm={() => api.delete(`/admin/users/${u.id}`).then(load)}>
              <Button size="small" danger={u.is_active} icon={u.is_active ? <LockOutlined /> : <UnlockOutlined />}>{u.is_active ? "Khóa" : "Mở"}</Button></Popconfirm>}
          </Space> },
        ]} />
      {edit && <UserForm ctx={ctx} edit={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); load(); }} />}
      {am && <AmUnits u={am} ctx={ctx} onClose={() => setAm(null)} />}
      {importing && <ImportUsersModal onClose={() => setImporting(false)} onDone={load} />}
      {inactive && <InactiveUsersModal onClose={() => setInactive(false)} onDone={load} />}
      {handover && <HandoverModal user={handover} onClose={() => setHandover(null)} onDone={() => { setHandover(null); load(); }} />}
    </>
  );
}

function Roles({ ctx }: { ctx: Ctx }) {
  const [roles, setRoles] = useState<any[]>([]);
  const [perms, setPerms] = useState<any[]>([]);
  const [sel, setSel] = useState<number>();
  const [draft, setDraft] = useState<any>();
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();
  const load = () => api.get("/admin/roles").then((r) => { setRoles(r.data); return r.data; });
  useEffect(() => { load().then((d: any[]) => d.length && setSel(d[0].id)); api.get("/admin/permissions").then((r) => setPerms(r.data)); }, []);
  useEffect(() => { const r = roles.find((x) => x.id === sel); if (r) setDraft({ ...r }); }, [sel, roles]);
  const modules = useMemo(() => [...new Set(perms.map((p) => p.module))], [perms]);
  const dirty = draft && JSON.stringify([...draft.permissions].sort()) + draft.data_scope + draft.level !==
    JSON.stringify([...(roles.find((x) => x.id === sel)?.permissions ?? [])].sort()) + roles.find((x) => x.id === sel)?.data_scope + roles.find((x) => x.id === sel)?.level;
  const save = async () => { await api.put(`/admin/roles/${draft.id}`, draft); message.success("Đã lưu phân quyền"); load(); };
  const create = async () => { const v = await form.validateFields(); const r = await api.post("/admin/roles", { ...v, permissions: [] }); setCreating(false); form.resetFields(); await load(); setSel(r.data.id); };
  const levelsWithRoles = ctx.levels.filter((l) => roles.some((r) => r.level === l.value));

  return (
    <Row gutter={16}>
      <Col xs={24} lg={8}>
        <Button block type="dashed" icon={<PlusOutlined />} style={{ marginBottom: 8 }} onClick={() => setCreating(true)}>Tạo vai trò mới</Button>
        {levelsWithRoles.map((l) => (
          <div key={l.value} style={{ marginBottom: 8 }}>
            <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", margin: "6px 0" }}>{l.label}</div>
            {roles.filter((r) => r.level === l.value).map((r) => (
              <Card key={r.id} size="small" hoverable onClick={() => setSel(r.id)} style={{ marginBottom: 6, borderColor: sel === r.id ? "#1d4ed8" : undefined, background: sel === r.id ? "#eff6ff" : undefined }}>
                <Space style={{ width: "100%", justifyContent: "space-between" }}><b>{r.name}</b><Tag>{r.user_count} TK</Tag></Space>
                <div className="muted" style={{ fontSize: 12 }}>{SCOPE[r.data_scope]} · {r.permissions.length} quyền</div>
              </Card>))}
          </div>))}
      </Col>
      <Col xs={24} lg={16}>
        {draft ? <Card size="small" title={<Space><SafetyCertificateOutlined />{draft.name}</Space>}
          extra={<Space>
            {draft.user_count === 0 && draft.code !== "admin" && <Popconfirm title="Xóa vai trò này?" onConfirm={() => api.delete(`/admin/roles/${draft.id}`).then(() => { setSel(undefined); setDraft(undefined); load(); })}>
              <Button danger icon={<DeleteOutlined />} size="small">Xóa</Button></Popconfirm>}
            <Button type="primary" size="small" disabled={!dirty || draft.code === "admin"} onClick={save}>Lưu thay đổi</Button></Space>}>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>{draft.description}</Typography.Paragraph>
          <Space wrap style={{ marginBottom: 12 }}>
            <span>Cấp</span><Select size="small" style={{ width: 160 }} value={draft.level} disabled={draft.code === "admin"} onChange={(v) => setDraft({ ...draft, level: v })} options={ctx.levels} />
            <span>Phạm vi dữ liệu</span><Select size="small" style={{ width: 220 }} value={draft.data_scope} disabled={draft.code === "admin"} onChange={(v) => setDraft({ ...draft, data_scope: v })}
              options={Object.entries(SCOPE).map(([value, label]) => ({ value, label }))} />
          </Space>
          {draft.code === "admin" && <Alert type="warning" showIcon style={{ marginBottom: 8 }} message="Vai trò Quản trị hệ thống luôn có toàn quyền, không chỉnh sửa." />}
          <Row gutter={[12, 12]}>
            {modules.map((m) => (
              <Col xs={24} md={12} key={m}>
                <Card size="small" type="inner" title={m}>
                  {perms.filter((p) => p.module === m).map((p) => (
                    <div key={p.code}><Checkbox disabled={draft.code === "admin"} checked={draft.permissions.includes(p.code)}
                      onChange={(e) => setDraft({ ...draft, permissions: e.target.checked ? [...draft.permissions, p.code] : draft.permissions.filter((x: string) => x !== p.code) })}>
                      {p.name}</Checkbox></div>))}
                </Card>
              </Col>))}
          </Row>
        </Card> : <Empty />}
      </Col>
      <Modal open={creating} title="Tạo vai trò mới" onOk={create} onCancel={() => setCreating(false)} okText="Tạo">
        <Form form={form} layout="vertical" initialValues={{ level: "xa", data_scope: "unit" }}>
          <Form.Item name="code" label="Mã vai trò" rules={[{ required: true, pattern: /^[a-z_]{3,40}$/, message: "chữ thường và dấu _" }]}><Input placeholder="vd: ke_toan_xa" /></Form.Item>
          <Form.Item name="name" label="Tên chức danh" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="level" label="Cấp"><Select options={ctx.levels} /></Form.Item>
          <Form.Item name="data_scope" label="Phạm vi dữ liệu"><Select options={Object.entries(SCOPE).map(([value, label]) => ({ value, label }))} /></Form.Item>
          <Form.Item name="description" label="Mô tả"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="duties" label="Công việc chính (phân tách bằng |)"><Input /></Form.Item>
        </Form>
      </Modal>
    </Row>
  );
}

const CATS: [string, string, string, string][] = [  // [mã, tên, loại hình, cấp]
  ["ubnd_tinh", "UBND tỉnh", "hanh_chinh", "tinh"], ["van_phong", "Văn phòng UBND tỉnh", "hanh_chinh", "tinh"],
  ["so_nganh", "Sở, ban, ngành", "hanh_chinh", "tinh"], ["ubnd_xa", "UBND xã, phường", "hanh_chinh", "xa"],
  ["thpt", "Trường THPT", "giao_duc", "tinh"], ["thcs", "Trường THCS", "giao_duc", "xa"],
  ["tieu_hoc", "Trường Tiểu học", "giao_duc", "xa"], ["mam_non", "Trường Mầm non", "giao_duc", "xa"],
];

/** Danh mục đơn vị cho quản trị: chỉ thông tin hành chính + số tài khoản (không hiển thị điểm đánh giá) */
function UnitsCatalog() {
  const { can } = useAuth();
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [f, setF] = useState<any>({ page: 1, size: 15 });
  const [regions, setRegions] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  const load = () => api.get("/admin/units", { params: f }).then((r) => setData(r.data));
  useEffect(() => { load(); }, [f]);
  useEffect(() => { api.get("/regions").then((r) => setRegions(r.data)); }, []);
  const open = (u: any) => { setEdit(u); form.resetFields(); if (u.id) form.setFieldsValue(u); };
  const save = async () => {
    const v = await form.validateFields();
    const cat = CATS.find((c) => c[0] === v.category)!;
    const body = { ...edit, ...v, unit_type: cat[2], level: cat[3], is_active: v.is_active ?? true };
    if (edit.id) await api.put(`/units/${edit.id}`, body); else await api.post("/units", body);
    message.success("Đã lưu đơn vị"); setEdit(null); load();
  };
  return (
    <>
      <Space style={{ marginBottom: 12 }} wrap>
        <Input.Search allowClear placeholder="Tên hoặc mã đơn vị" style={{ width: 240 }} onSearch={(q) => setF({ ...f, q, page: 1 })} />
        <Select allowClear placeholder="Phân loại" style={{ width: 190 }} onChange={(v) => setF({ ...f, category: v, page: 1 })} options={CATS.map((c) => ({ value: c[0], label: c[1] }))} />
        <Select allowClear showSearch optionFilterProp="label" placeholder="Địa bàn" style={{ width: 200 }} onChange={(v) => setF({ ...f, region_id: v, page: 1 })}
          options={regions.map((r) => ({ value: r.id, label: r.name }))} />
        {can("catalog.manage") && <Button type="primary" icon={<PlusOutlined />} onClick={() => open({})}>Thêm đơn vị</Button>}
      </Space>
      <Table size="small" rowKey="id" dataSource={data.items}
        pagination={{ current: f.page, pageSize: f.size, total: data.total, showTotal: (t) => `${t} đơn vị`, onChange: (page, size) => setF({ ...f, page, size }) }}
        columns={[
          { title: "Mã", dataIndex: "code", width: 130 },
          { title: "Tên đơn vị", dataIndex: "name" },
          { title: "Phân loại", dataIndex: "category_name", width: 170 },
          { title: "Cấp", dataIndex: "level", width: 70, render: (v) => (v === "tinh" ? "Tỉnh" : "Xã") },
          { title: "Địa bàn", dataIndex: "region_name", width: 170 },
          { title: "Người đứng đầu", dataIndex: "head_name", width: 160, responsive: ["lg"] },
          { title: "Tài khoản", dataIndex: "user_count", width: 90, align: "right", render: (v) => v ? <Tag color="blue">{v}</Tag> : <span className="muted">0</span> },
          { title: "Trạng thái", dataIndex: "is_active", width: 110, render: (v) => <Badge status={v ? "success" : "default"} text={v ? "Hoạt động" : "Ngừng"} /> },
          ...(can("catalog.manage") ? [{ title: "", key: "a", width: 70, render: (_: any, u: any) => <Button size="small" onClick={() => open(u)}>Sửa</Button> }] : []),
        ]} />
      <Modal open={!!edit} width={640} title={edit?.id ? `Sửa đơn vị ${edit.code}` : "Thêm đơn vị"} onOk={save} onCancel={() => setEdit(null)} okText="Lưu">
        <Form form={form} layout="vertical" initialValues={{ is_active: true }}>
          <Row gutter={12}>
            <Col span={8}><Form.Item name="code" label="Mã đơn vị" rules={[{ required: true }]}><Input disabled={!!edit?.id} /></Form.Item></Col>
            <Col span={16}><Form.Item name="name" label="Tên đơn vị" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="category" label="Phân loại" rules={[{ required: true }]}><Select options={CATS.map((c) => ({ value: c[0], label: c[1] }))} /></Form.Item></Col>
            <Col span={12}><Form.Item name="region_id" label="Địa bàn" rules={[{ required: true }]}>
              <Select showSearch optionFilterProp="label" options={regions.map((r) => ({ value: r.id, label: r.name }))} /></Form.Item></Col>
            <Col span={12}><Form.Item name="head_name" label="Người đứng đầu"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="phone" label="Điện thoại"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="email" label="Email"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="address" label="Địa chỉ"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="staff_count" label="Số CBCCVC/GV"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="student_count" label="Số học sinh"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="is_active" label="Trạng thái"><Select options={[{ value: true, label: "Hoạt động" }, { value: false, label: "Ngừng hoạt động" }]} /></Form.Item></Col>
          </Row>
        </Form>
      </Modal>
    </>
  );
}

function AuditLogs() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [f, setF] = useState<any>({ page: 1, size: 20 });
  useEffect(() => { api.get("/admin/audit-logs", { params: f }).then((r) => setData(r.data)); }, [f]);
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search allowClear placeholder="Người dùng" onSearch={(username) => setF({ ...f, username, page: 1 })} />
        <Select allowClear placeholder="Hành động" style={{ width: 170 }} onChange={(action) => setF({ ...f, action, page: 1 })}
          options={["login", "create", "update", "lock", "unlock", "reset_password", "tiep_nhan", "phan_cong", "trinh", "bao_cao", "xac_nhan", "cascade", "upload", "export"].map((v) => ({ value: v, label: v }))} />
      </Space>
      <Table size="small" rowKey="id" dataSource={data.items} pagination={{ current: f.page, pageSize: f.size, total: data.total, onChange: (page, size) => setF({ ...f, page, size }) }} columns={[
        { title: "Thời gian", dataIndex: "created_at", width: 150, render: (v) => dayjs(v).format("HH:mm:ss DD/MM/YY") },
        { title: "Người dùng", dataIndex: "username", width: 150 }, { title: "Hành động", dataIndex: "action", width: 120, render: (v) => <Tag>{v}</Tag> },
        { title: "Đối tượng", key: "e", width: 170, render: (_, a: any) => a.entity && `${a.entity} #${a.entity_id ?? ""}` },
        { title: "Chi tiết", dataIndex: "detail", render: (v) => v && <code style={{ fontSize: 11 }}>{JSON.stringify(v).slice(0, 160)}</code> },
        { title: "IP", dataIndex: "ip", width: 110, responsive: ["lg"] },
      ]} />
    </>
  );
}

/** Các mục quản trị – mỗi mục là một trang riêng trên sidebar (đường dẫn /admin/<mục>) */
export const ADMIN_SECTIONS: { key: string; title: string; sub: string; perm: string[] }[] = [
  { key: "setup", title: "Thiết lập tỉnh mới", sub: "Các bước đưa hệ thống vào vận hành cho một tỉnh/thành – trạng thái tự kiểm tra", perm: ["role.manage"] },
  { key: "users", title: "Tài khoản người dùng", sub: "Cấp, khóa, cấp lại mật khẩu, nhập/xuất Excel, chuyển giao công việc", perm: ["user.manage"] },
  { key: "sessions", title: "Phiên đăng nhập", sub: "Ai đang đăng nhập, thiết bị, IP – buộc đăng xuất từ xa", perm: ["user.manage"] },
  { key: "permissions", title: "Vai trò & phân quyền", sub: "Tạo vai trò, gán quyền theo phân hệ, phạm vi dữ liệu", perm: ["role.manage"] },
  { key: "units", title: "Danh mục đơn vị", sub: "Thông tin hành chính của cơ quan, trường học (không có số liệu đánh giá)", perm: ["catalog.manage", "user.manage"] },
  { key: "regions", title: "Danh mục địa bàn", sub: "Xã, phường, đặc khu thuộc tỉnh", perm: ["catalog.manage"] },
  { key: "settings", title: "Tham số & chính sách", sub: "Chính sách mật khẩu, khóa đăng nhập, phiên, chế độ demo", perm: ["role.manage"] },
  { key: "periods", title: "Kỳ đánh giá", sub: "Tạo kỳ, đặt kỳ hiện hành, khóa số liệu kỳ đã công bố", perm: ["role.manage"] },
  { key: "announcements", title: "Thông báo hệ thống", sub: "Gửi thông báo bảo trì, hướng dẫn tới người dùng theo cấp", perm: ["role.manage"] },
  { key: "monitor", title: "Giám sát & sao lưu", sub: "Tình trạng máy chủ, cơ sở dữ liệu, lỗi; sao lưu CSDL", perm: ["role.manage"] },
  { key: "audit", title: "Nhật ký & bảo mật", sub: "Nhật ký hoạt động, xuất Excel, cảnh báo hành vi bất thường", perm: ["audit.view"] },
  { key: "api", title: "Tích hợp API", sub: "Khóa API cho hệ thống ngoài (LGSP, VBĐH)", perm: ["role.manage"] },
];

export default function Admin() {
  const { can } = useAuth();
  const { section } = useParams();
  const [ctx, setCtx] = useState<Ctx>();
  useEffect(() => { if (can("user.manage")) api.get("/admin/context").then((r) => setCtx(r.data)); }, []);
  const allowed = ADMIN_SECTIONS.filter((x) => can(...x.perm));
  const cur = allowed.find((x) => x.key === section);
  if (!cur) return <Navigate to={`/admin/${allowed[0]?.key ?? "users"}`} replace />;
  if (!ctx) return <PageHeader title={cur.title} sub={cur.sub} />;
  const body: Record<string, JSX.Element> = {
    setup: <AdminSetup />, users: <Users ctx={ctx} />, sessions: <SessionsTab />, permissions: <Roles ctx={ctx} />, units: <UnitsCatalog />,
    regions: <><CatalogImportCard /><RegionsTab /></>, settings: <SettingsTab />, periods: <PeriodsTab />, announcements: <AnnouncementsTab />,
    monitor: <MonitorTab />, audit: <AuditTab />, api: <ApiKeysTab />,
  };
  return (
    <>
      <PageHeader title={cur.title} sub={ctx.is_super ? cur.sub : `${cur.sub} · Phạm vi: ${ctx.scope}`} />
      {!ctx.is_super && cur.key === "users" && <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Phân cấp quản trị"
        description="Bạn cấp tài khoản cho cán bộ xã/phường và các trường trên địa bàn. Vai trò cấp tỉnh, sở và tài khoản quản trị do Quản trị hệ thống cấp tỉnh cấp." />}
      <Card size="small">{body[cur.key]}</Card>
    </>
  );
}
