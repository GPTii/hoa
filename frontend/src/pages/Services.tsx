/** Danh mục dịch vụ / giải pháp công nghệ (đề cương 2.2, 4.2) và dịch vụ đơn vị đang sử dụng */
import { useEffect, useState } from "react";
import { Badge, Button, Card, DatePicker, Form, Input, InputNumber, Modal, Popconfirm, Progress, Select, Space, Table, Tag, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader, PILLAR_NAMES, money, scoreColor } from "../components/common";

const CAT: Record<string, string> = { dieu_hanh: "Điều hành", ky_so: "Chữ ký số", dvc: "Dịch vụ công / thanh toán", attt: "An toàn thông tin",
  ha_tang: "Hạ tầng", giao_duc: "Giáo dục số", dao_tao: "Đào tạo", du_lieu: "Dữ liệu" };
const UT: Record<string, string> = { hanh_chinh: "Hành chính", giao_duc: "Giáo dục" };
export const SVC_STATUS: Record<string, [string, string]> = { dang_dung: ["success", "Đang dùng"], dung_thu: ["processing", "Dùng thử"], het_han: ["error", "Hết hạn"], ngung: ["default", "Ngừng"] };

export default function Services() {
  const { can } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  const load = () => api.get("/services").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    const v = await form.validateFields();
    if (edit.id) await api.put(`/services/${edit.id}`, { ...v, code: edit.code }); else await api.post("/services", v);
    message.success("Đã lưu dịch vụ"); setEdit(null); load();
  };
  return (
    <>
      <PageHeader title="Danh mục dịch vụ, giải pháp công nghệ" sub="Các dịch vụ số đơn vị có thể sử dụng – căn cứ đề xuất giải pháp và phân tích AM"
        extra={can("unit.manage") && <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEdit({}); form.resetFields(); }}>Thêm dịch vụ</Button>} />
      <Card size="small">
        <Table size="small" rowKey="id" dataSource={rows} pagination={{ pageSize: 20 }} columns={[
          { title: "Mã", dataIndex: "code", width: 120 },
          { title: "Dịch vụ / giải pháp", dataIndex: "name", render: (v, s: any) => <div><b>{v}</b><div className="muted" style={{ fontSize: 12 }}>{s.description}</div></div> },
          { title: "Nhóm", dataIndex: "category", width: 160, render: (v) => CAT[v] ?? v, filters: Object.entries(CAT).map(([value, text]) => ({ value, text })), onFilter: (v, s: any) => s.category === v },
          { title: "Trụ cột", dataIndex: "pillar_code", width: 120, render: (v) => v && <Tag>{PILLAR_NAMES[v]}</Tag> },
          { title: "Áp dụng", dataIndex: "unit_types", width: 150, render: (v: string[]) => v.map((x) => <Tag key={x}>{UT[x]}</Tag>) },
          { title: "Giá/tháng", dataIndex: "monthly_price", width: 120, align: "right", render: (v) => money(v) },
          { title: "Đơn vị đang dùng", dataIndex: "active_units", width: 120, align: "right" },
          { title: "Nhà cung cấp", dataIndex: "provider", width: 110 },
          ...(can("unit.manage") ? [{ title: "", key: "a", width: 70, render: (_: any, s: any) => <Button size="small" onClick={() => { setEdit(s); form.setFieldsValue(s); }}>Sửa</Button> }] : []),
        ]} />
      </Card>
      <Modal open={!!edit} title={edit?.id ? `Sửa ${edit.code}` : "Thêm dịch vụ"} onOk={save} onCancel={() => setEdit(null)} okText="Lưu">
        <Form form={form} layout="vertical" initialValues={{ provider: "VNPT", unit_types: ["hanh_chinh", "giao_duc"] }}>
          <Form.Item name="code" label="Mã" rules={[{ required: true }]}><Input disabled={!!edit?.id} /></Form.Item>
          <Form.Item name="name" label="Tên dịch vụ / giải pháp" rules={[{ required: true }]}><Input /></Form.Item>
          <Space wrap>
            <Form.Item name="category" label="Nhóm" rules={[{ required: true }]}><Select style={{ width: 200 }} options={Object.entries(CAT).map(([value, label]) => ({ value, label }))} /></Form.Item>
            <Form.Item name="pillar_code" label="Trụ cột DTI liên quan"><Select allowClear style={{ width: 180 }} options={Object.entries(PILLAR_NAMES).map(([value, label]) => ({ value, label }))} /></Form.Item>
          </Space>
          <Form.Item name="unit_types" label="Áp dụng cho" rules={[{ required: true }]}><Select mode="multiple" options={Object.entries(UT).map(([value, label]) => ({ value, label }))} /></Form.Item>
          <Space><Form.Item name="monthly_price" label="Giá/tháng (đ)"><InputNumber min={0} style={{ width: 160 }} /></Form.Item>
            <Form.Item name="provider" label="Nhà cung cấp"><Input /></Form.Item></Space>
          <Form.Item name="description" label="Mô tả"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}

/** Bảng dịch vụ đơn vị đang dùng – Sở KH&CN / AM phụ trách cập nhật được */
export function UnitServicesTable({ unitId, unitType, services, onChanged }: { unitId: number; unitType: string; services: any[]; onChanged: () => void }) {
  const { can, user } = useAuth();
  const editable = can("unit.manage") || can("am.view");
  const [catalog, setCatalog] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  useEffect(() => { if (editable) api.get("/services").then((r) => setCatalog(r.data.filter((s: any) => s.unit_types.includes(unitType)))); }, []);
  const save = async () => {
    const v = await form.validateFields();
    await api.post(`/units/${unitId}/services`, { ...v, start_date: v.start_date?.format("YYYY-MM-DD"), end_date: v.end_date?.format("YYYY-MM-DD") });
    message.success("Đã lưu"); setEdit(null); onChanged();
  };
  return (
    <>
      {editable && <Button size="small" icon={<PlusOutlined />} style={{ marginBottom: 8 }} onClick={() => { setEdit({}); form.resetFields(); form.setFieldsValue({ status: "dang_dung", usage_level: 50 }); }}>Thêm / cập nhật dịch vụ</Button>}
      <Table size="small" rowKey="id" pagination={false} dataSource={services} columns={[
        { title: "Dịch vụ / giải pháp", dataIndex: "name" },
        { title: "Trạng thái", dataIndex: "status", render: (v) => <Badge status={SVC_STATUS[v][0] as any} text={SVC_STATUS[v][1]} /> },
        { title: "Hết hạn", dataIndex: "end_date", render: (v) => v && dayjs(v).format("DD/MM/YYYY") },
        { title: "Mức khai thác", dataIndex: "usage_level", width: 180, render: (v) => <Progress percent={v} size="small" strokeColor={scoreColor(v)} /> },
        { title: "Phí/tháng", dataIndex: "monthly_fee", align: "right", render: (v) => money(v), responsive: ["md"] },
        ...(editable ? [{ title: "", key: "a", width: 120, render: (_: any, s: any) => <Space>
          <Button size="small" onClick={() => { setEdit(s); form.setFieldsValue({ ...s, start_date: s.start_date && dayjs(s.start_date), end_date: s.end_date && dayjs(s.end_date) }); }}>Sửa</Button>
          <Popconfirm title="Xóa dịch vụ khỏi đơn vị?" onConfirm={() => api.delete(`/units/${unitId}/services/${s.id}`).then(onChanged)}><Button size="small" danger>Xóa</Button></Popconfirm></Space> }] : []),
      ]} />
      <Modal open={!!edit} title="Dịch vụ đơn vị sử dụng" onOk={save} onCancel={() => setEdit(null)} okText="Lưu">
        <Form form={form} layout="vertical">
          <Form.Item name="service_id" label="Dịch vụ" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" disabled={!!edit?.id} options={catalog.map((s) => ({ value: s.id, label: s.name }))} /></Form.Item>
          <Space wrap>
            <Form.Item name="status" label="Trạng thái"><Select style={{ width: 150 }} options={Object.entries(SVC_STATUS).map(([value, [, label]]) => ({ value, label }))} /></Form.Item>
            <Form.Item name="usage_level" label="Mức khai thác (%)"><InputNumber min={0} max={100} /></Form.Item>
            <Form.Item name="monthly_fee" label="Phí/tháng"><InputNumber min={0} style={{ width: 140 }} /></Form.Item>
          </Space>
          <Space><Form.Item name="start_date" label="Bắt đầu"><DatePicker format="DD/MM/YYYY" /></Form.Item>
            <Form.Item name="end_date" label="Hết hạn"><DatePicker format="DD/MM/YYYY" /></Form.Item></Space>
        </Form>
      </Modal>
    </>
  );
}
