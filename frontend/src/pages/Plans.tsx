/** Kế hoạch cải thiện CĐS – lập từ đề xuất, ban hành, theo dõi tiến độ (đề cương 4.7) */
import { useEffect, useState } from "react";
import { Alert, Button, Card, Checkbox, DatePicker, Descriptions, Empty, Form, Input, InputNumber, Modal, Popconfirm, Progress, Radio, Select, Space, Table, Tag, Typography, message } from "antd";
import { DownloadOutlined, FileAddOutlined } from "@ant-design/icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import dayjs from "dayjs";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { PageHeader, Score, SEVERITY } from "../components/common";

const ST: Record<string, string> = { chua_lam: "default", dang_lam: "processing", hoan_thanh: "success" };
const PST: Record<string, string> = { du_thao: "default", ban_hanh: "blue", hoan_thanh: "green" };
const COST: Record<string, string> = { thap: "Thấp", trung_binh: "Trung bình", cao: "Cao" };

/** Hộp thoại lập kế hoạch từ các nhóm giải pháp đã được hệ thống đề xuất */
export function CreatePlanModal({ groups, onClose }: { groups: any[]; onClose: () => void }) {
  const { user } = useAuth();
  const nav = useNavigate();
  const [form] = Form.useForm();
  const [units, setUnits] = useState<any[]>([]);
  useEffect(() => { api.get("/units", { params: { size: 500 } }).then((r) => setUnits(r.data.items)); }, []);
  const scope = Form.useWatch("scope", form);
  const submit = async () => {
    const v = await form.validateFields();
    const r = await api.post("/plans", {
      title: v.title, solution_ids: v.solution_ids, only_high: v.only_high, start_date: v.start_date?.format("YYYY-MM-DD"),
      unit_id: v.scope === "unit" ? v.unit_id : undefined, region_id: v.scope === "region" ? user?.region?.id : undefined,
    });
    message.success(`Đã lập kế hoạch ${r.data.item_count} hạng mục`); onClose(); nav(`/plans/${r.data.id}`);
  };
  return (
    <Modal open width={720} title="Lập kế hoạch cải thiện chuyển đổi số" onOk={submit} onCancel={onClose} okText="Lập kế hoạch">
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Hệ thống sinh sẵn các hạng mục từ đề xuất (đơn vị, nội dung, thời hạn theo thời lượng giải pháp, mức ưu tiên, điểm hiện trạng làm mốc). Bạn điều chỉnh rồi ban hành – quyết định cuối cùng thuộc người quản lý." />
      <Form form={form} layout="vertical" initialValues={{ scope: user?.region ? "region" : user?.unit ? "unit" : "all", unit_id: user?.unit?.id,
        title: `Kế hoạch nâng cao mức độ chuyển đổi số ${user?.region?.name ?? user?.unit?.name ?? ""}`, start_date: dayjs(),
        solution_ids: groups.filter((g) => g.high_count > 0).map((g) => g.id) }}>
        <Form.Item name="title" label="Tên kế hoạch" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="scope" label="Phạm vi"><Radio.Group options={[
          ...(user?.region ? [{ value: "region", label: `Toàn địa bàn ${user.region.name}` }] : []),
          { value: "unit", label: "Một đơn vị" }, ...(user?.role.data_scope === "all" || user?.role.data_scope === "giao_duc" ? [{ value: "all", label: "Toàn bộ phạm vi quản lý" }] : []),
        ]} /></Form.Item>
        {scope === "unit" && <Form.Item name="unit_id" label="Đơn vị" rules={[{ required: true }]}>
          <Select showSearch optionFilterProp="label" options={units.map((u) => ({ value: u.id, label: u.name }))} /></Form.Item>}
        <Form.Item name="solution_ids" label="Nhóm giải pháp đưa vào kế hoạch" rules={[{ required: true }]}>
          <Checkbox.Group style={{ display: "grid", gap: 4 }} options={groups.map((g) => ({ value: g.id,
            label: <span>{g.name} <span className="muted">· {g.unit_count} đơn vị{g.high_count ? ` · ${g.high_count} ưu tiên cao` : ""}</span></span> }))} /></Form.Item>
        <Space>
          <Form.Item name="start_date" label="Ngày bắt đầu"><DatePicker format="DD/MM/YYYY" /></Form.Item>
          <Form.Item name="only_high" valuePropName="checked" label=" "><Checkbox>Chỉ đơn vị ưu tiên cao</Checkbox></Form.Item>
        </Space>
      </Form>
    </Modal>
  );
}

function PlanDetail({ id }: { id: number }) {
  const { user } = useAuth();
  const [p, setP] = useState<any>();
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  const load = () => api.get(`/plans/${id}`).then((r) => setP(r.data));
  useEffect(() => { load(); }, [id]);
  if (!p) return null;
  const saveItem = async () => {
    const v = await form.validateFields();
    await api.put(`/plans/items/${edit.id}`, { ...v, start_date: v.start_date?.format("YYYY-MM-DD"), end_date: v.end_date?.format("YYYY-MM-DD") });
    message.success("Đã cập nhật"); setEdit(null); load();
  };
  const mineOnly = (i: any) => !p.can_edit && user?.unit?.id === i.unit_id;
  return (
    <>
      <PageHeader title={p.title} sub={`${p.owner ?? ""} · ${p.item_count} hạng mục · ${p.units} đơn vị`}
        extra={<>
          <Tag color={PST[p.status]}>{p.status_name}</Tag>
          {p.can_edit && p.status === "du_thao" && <Popconfirm title="Ban hành kế hoạch? Các đơn vị sẽ cập nhật tiến độ hạng mục của mình."
            onConfirm={() => api.put(`/plans/${id}`, { status: "ban_hanh" }).then(load)}><Button type="primary">Ban hành</Button></Popconfirm>}
          {p.can_edit && p.status === "ban_hanh" && p.done_count === p.item_count && <Button onClick={() => api.put(`/plans/${id}`, { status: "hoan_thanh" }).then(load)}>Đóng kế hoạch</Button>}
          <Button icon={<DownloadOutlined />} onClick={() => download(`/plans/${id}/export.xlsx`, {}, `ke_hoach_${id}.xlsx`)}>Xuất Excel</Button>
        </>} />
      <Card size="small" style={{ marginBottom: 12 }}>
        <Descriptions size="small" column={{ xs: 1, md: 4 }} items={[
          { label: "Tiến độ chung", children: <Progress percent={p.progress} size="small" style={{ width: 160 }} /> },
          { label: "Hoàn thành", children: `${p.done_count}/${p.item_count} hạng mục` },
          { label: "Quá hạn", children: p.items.filter((i: any) => i.overdue).length },
          { label: "Lập ngày", children: dayjs(p.created_at).format("DD/MM/YYYY") },
        ]} />
      </Card>
      <Card size="small">
        <Table size="small" rowKey="id" dataSource={p.items} pagination={{ pageSize: 12 }} scroll={{ x: 1750 }} columns={[
          { title: "Đơn vị", dataIndex: "unit_name", width: 200, render: (v, i: any) => <Link to={`/units/${i.unit_id}`}>{v}</Link> },
          { title: "Nhóm giải pháp", dataIndex: "solution", width: 220, render: (v, i: any) => <div>{v}<div className="muted" style={{ fontSize: 12 }}>{i.pillar}</div></div> },
          { title: "Nội dung thực hiện", dataIndex: "action", width: 340 },
          { title: "Chịu trách nhiệm", dataIndex: "responsible", width: 170 },
          { title: "Thời hạn", key: "t", width: 140, render: (_, i: any) => <span style={{ color: i.overdue ? "#dc2626" : undefined }}>{i.start_date && dayjs(i.start_date).format("DD/MM")} – {i.end_date && dayjs(i.end_date).format("DD/MM/YY")}</span> },
          { title: "Ưu tiên", dataIndex: "priority", width: 100, render: (v) => <Tag color={SEVERITY[v]?.color}>{SEVERITY[v]?.text}</Tag> },
          { title: "Chi phí", dataIndex: "cost_level", width: 90, render: (v) => COST[v] },
          { title: "Mốc → DTI nay", key: "s", width: 110, render: (_, i: any) => <span><Score v={i.baseline_score} /> → <Score v={p.dti_now[i.unit_id]} /></span> },
          { title: "Tiến độ", key: "pr", width: 170, render: (_, i: any) => <div><Tag color={ST[i.status]}>{i.status_name}</Tag><Progress percent={i.progress} size="small" /></div> },
          { title: "", key: "a", width: 90, fixed: "right", render: (_, i: any) => (p.can_edit || mineOnly(i)) && p.status !== "hoan_thanh" &&
            <Button size="small" onClick={() => { setEdit(i); form.setFieldsValue({ ...i, start_date: i.start_date && dayjs(i.start_date), end_date: i.end_date && dayjs(i.end_date) }); }}>
              {p.can_edit ? "Sửa" : "Cập nhật"}</Button> },
        ]} />
      </Card>
      <Modal open={!!edit} title={edit?.unit_name} onOk={saveItem} onCancel={() => setEdit(null)} okText="Lưu">
        <Form form={form} layout="vertical">
          {p.can_edit && <>
            <Form.Item name="action" label="Nội dung thực hiện"><Input.TextArea rows={3} /></Form.Item>
            <Form.Item name="responsible" label="Người/đơn vị chịu trách nhiệm"><Input /></Form.Item>
            <Space><Form.Item name="start_date" label="Bắt đầu"><DatePicker format="DD/MM/YYYY" /></Form.Item>
              <Form.Item name="end_date" label="Hoàn thành"><DatePicker format="DD/MM/YYYY" /></Form.Item></Space>
          </>}
          <Space><Form.Item name="status" label="Trạng thái"><Select style={{ width: 170 }} options={[{ value: "chua_lam", label: "Chưa thực hiện" }, { value: "dang_lam", label: "Đang thực hiện" }, { value: "hoan_thanh", label: "Hoàn thành" }]} /></Form.Item>
            <Form.Item name="progress" label="Tiến độ (%)"><InputNumber min={0} max={100} /></Form.Item></Space>
        </Form>
      </Modal>
    </>
  );
}

export default function Plans() {
  const { id } = useParams();
  const { can } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  useEffect(() => { if (!id) { api.get("/plans").then((r) => setRows(r.data)); api.get("/analytics/planning").then((r) => setGroups(r.data.groups)); } }, [id]);
  if (id) return <PlanDetail id={Number(id)} />;
  return (
    <>
      <PageHeader title="Kế hoạch cải thiện chuyển đổi số" sub="Lập từ đề xuất của hệ thống → ban hành → các đơn vị cập nhật tiến độ → đánh giá hiệu quả qua DTI các kỳ sau"
        extra={can("plan.manage") && <Button type="primary" icon={<FileAddOutlined />} onClick={() => setCreating(true)}>Lập kế hoạch mới</Button>} />
      <Card size="small">
        {rows.length ? <Table size="small" rowKey="id" dataSource={rows} pagination={{ pageSize: 15 }} columns={[
          { title: "Kế hoạch", dataIndex: "title", render: (v, p: any) => <div><Link to={`/plans/${p.id}`}><b>{v}</b></Link><div className="muted" style={{ fontSize: 12 }}>{p.owner}</div></div> },
          { title: "Phạm vi", key: "s", render: (_, p: any) => p.unit_name ?? p.region_name ?? "Toàn phạm vi" },
          { title: "Hạng mục", dataIndex: "item_count", align: "right" }, { title: "Đơn vị", dataIndex: "units", align: "right" },
          { title: "Tiến độ", dataIndex: "progress", width: 160, render: (v) => <Progress percent={v} size="small" /> },
          { title: "Trạng thái", dataIndex: "status_name", render: (v, p: any) => <Tag color={PST[p.status]}>{v}</Tag> },
          { title: "Ngày lập", dataIndex: "created_at", render: (v) => dayjs(v).format("DD/MM/YYYY") },
        ]} /> : <Empty description="Chưa có kế hoạch – vào Hỗ trợ hoạch định hoặc bấm 'Lập kế hoạch mới'" />}
      </Card>
      {creating && <CreatePlanModal groups={groups} onClose={() => setCreating(false)} />}
      <Typography.Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12 }}>Gợi ý: đánh giá hiệu quả kế hoạch bằng cách so sánh "điểm mốc" của từng hạng mục với DTI của đơn vị ở các kỳ sau.</Typography.Paragraph>
    </>
  );
}
