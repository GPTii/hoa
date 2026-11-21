import { useEffect, useState } from "react";
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Delta, LevelTag, PageHeader, PeriodSelect, Score, UNIT_TYPE, useRegions } from "../components/common";

const CATS = [
  ["ubnd_tinh", "UBND tỉnh"], ["van_phong", "Văn phòng UBND tỉnh"], ["so_nganh", "Sở, ban, ngành"], ["ubnd_xa", "UBND xã, phường"],
  ["thpt", "Trường THPT"], ["thcs", "Trường THCS"], ["tieu_hoc", "Trường Tiểu học"], ["mam_non", "Trường Mầm non"],
];

export default function Units() {
  const { can } = useAuth();
  const regions = useRegions();
  const [period, setPeriod] = useState<string>();
  const [f, setF] = useState<any>({ page: 1, size: 20, sort: "name" });
  const [data, setData] = useState<any>({ total: 0, items: [] });
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const load = () => {
    if (!period) return;
    setLoading(true);
    api.get("/units", { params: { ...f, period } }).then((r) => setData(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, [f, period]);

  const save = async () => {
    const v = await form.validateFields();
    await api.post("/units", { ...v, level: ["ubnd_tinh", "van_phong", "so_nganh", "thpt"].includes(v.category) ? "tinh" : "xa",
      unit_type: ["ubnd_tinh", "van_phong", "so_nganh", "ubnd_xa"].includes(v.category) ? "hanh_chinh" : "giao_duc" });
    setOpen(false); form.resetFields(); load();
  };

  return (
    <>
      <PageHeader title="Quản lý đơn vị" sub="Cơ quan hành chính, cơ sở giáo dục theo địa bàn – mô hình chính quyền 2 cấp"
        extra={<>
          <PeriodSelect value={period} onChange={setPeriod} />
          {can("unit.manage") && <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>Thêm đơn vị</Button>}
        </>} />
      <Card size="small">
        <Space wrap style={{ marginBottom: 12 }}>
          <Input.Search placeholder="Tìm tên hoặc mã đơn vị" allowClear style={{ width: 260 }} onSearch={(q) => setF({ ...f, q, page: 1 })} />
          <Select allowClear placeholder="Loại hình" style={{ width: 180 }} onChange={(v) => setF({ ...f, unit_type: v, page: 1 })}
            options={Object.entries(UNIT_TYPE).map(([value, label]) => ({ value, label }))} />
          <Select allowClear placeholder="Phân loại" style={{ width: 180 }} onChange={(v) => setF({ ...f, category: v, page: 1 })}
            options={CATS.map(([value, label]) => ({ value, label }))} />
          <Select allowClear showSearch optionFilterProp="label" placeholder="Địa bàn" style={{ width: 200 }} onChange={(v) => setF({ ...f, region_id: v, page: 1 })}
            options={regions.map((r) => ({ value: r.id, label: r.name }))} />
          <Select value={f.sort} style={{ width: 170 }} onChange={(v) => setF({ ...f, sort: v })}
            options={[{ value: "name", label: "Sắp xếp: Tên" }, { value: "dti_desc", label: "DTI cao → thấp" }, { value: "dti_asc", label: "DTI thấp → cao" }]} />
        </Space>
        <Table rowKey="id" loading={loading} dataSource={data.items} size="middle"
          pagination={{ current: f.page, pageSize: f.size, total: data.total, showTotal: (t) => `${t} đơn vị`, onChange: (page, size) => setF({ ...f, page, size }) }}
          columns={[
            { title: "Mã", dataIndex: "code", width: 120 },
            { title: "Tên đơn vị", dataIndex: "name", render: (v, r: any) => <Link to={`/units/${r.id}`}>{v}</Link> },
            { title: "Phân loại", dataIndex: "category_name", responsive: ["md"] },
            { title: "Cấp", dataIndex: "level", render: (v) => (v === "tinh" ? "Tỉnh" : "Xã"), responsive: ["lg"] },
            { title: "Địa bàn", dataIndex: "region_name", responsive: ["md"] },
            { title: "DTI", dataIndex: "dti_score", align: "right", render: (v) => <Score v={v} /> },
            { title: "Mức độ", dataIndex: "dti_level", render: (v) => <LevelTag level={v} /> },
            { title: "± kỳ trước", dataIndex: "delta_prev", align: "right", render: (v) => <Delta v={v} />, responsive: ["lg"] },
            { title: "Hạng", dataIndex: "rank", align: "right", responsive: ["lg"] },
          ]} />
      </Card>
      <Modal title="Thêm đơn vị" open={open} onOk={save} onCancel={() => setOpen(false)} okText="Lưu">
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="Mã đơn vị" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="name" label="Tên đơn vị" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="category" label="Phân loại" rules={[{ required: true }]}><Select options={CATS.map(([value, label]) => ({ value, label }))} /></Form.Item>
          <Form.Item name="region_id" label="Địa bàn" rules={[{ required: true }]}>
            <Select showSearch optionFilterProp="label" options={regions.map((r) => ({ value: r.id, label: r.name }))} />
          </Form.Item>
          <Space><Form.Item name="staff_count" label="Số CBCCVC/giáo viên"><InputNumber min={0} /></Form.Item>
            <Form.Item name="student_count" label="Số học sinh"><InputNumber min={0} /></Form.Item></Space>
          <Form.Item name="head_name" label="Người đứng đầu"><Input /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}
