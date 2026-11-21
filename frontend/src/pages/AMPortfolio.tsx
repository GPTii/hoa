import { useEffect, useState } from "react";
import { Button, Card, Col, DatePicker, Form, Input, Modal, Popconfirm, Progress, Row, Select, Space, Table, Tabs, Tag, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Kpi, LevelTag, money, PageHeader, PeriodSelect, Score, SEVERITY, scoreColor } from "../components/common";


const ACT_COLOR: Record<string, string> = { tu_van: "blue", tap_huan: "purple", gia_han: "orange", trien_khai: "green", khao_sat: "cyan", ho_tro: "default" };

/** Kế hoạch chăm sóc đơn vị (đề cương 3.3) – lập, gợi ý tự động từ dữ liệu, cập nhật kết quả */
function CarePlansTab({ units }: { units: any[] }) {
  const [d, setD] = useState<any>({ items: [], activities: {} });
  const [unit, setUnit] = useState<number>();
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  const load = () => api.get("/am/care-plans", { params: { unit_id: unit } }).then((r) => setD(r.data));
  useEffect(() => { load(); }, [unit]);
  const save = async () => {
    const v = await form.validateFields();
    const body = { ...v, planned_date: v.planned_date.format("YYYY-MM-DD") };
    if (edit.id) await api.put(`/am/care-plans/${edit.id}`, body); else await api.post("/am/care-plans", body);
    message.success("Đã lưu"); setEdit(null); load();
  };
  const suggest = async () => {
    if (!unit) return message.warning("Chọn đơn vị để gợi ý");
    const r = await api.post("/am/care-plans/suggest", null, { params: { unit_id: unit } });
    message.success(`Đã thêm ${r.data.created} hoạt động gợi ý`); load();
  };
  return (
    <>
      <Space wrap style={{ marginBottom: 12 }}>
        <Select allowClear showSearch optionFilterProp="label" placeholder="Lọc theo đơn vị" style={{ width: 280 }} value={unit} onChange={setUnit}
          options={units.map((u: any) => ({ value: u.unit_id, label: u.name }))} />
        <Button onClick={suggest} disabled={!unit}>Gợi ý kế hoạch từ dữ liệu</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEdit({}); form.resetFields(); form.setFieldsValue({ unit_id: unit, status: "ke_hoach", activity: "tu_van", planned_date: dayjs().add(7, "day") }); }}>Thêm hoạt động</Button>
      </Space>
      <Table size="small" rowKey="id" dataSource={d.items} pagination={{ pageSize: 12 }} columns={[
        { title: "Ngày", dataIndex: "planned_date", width: 100, render: (v, c: any) => <span style={{ color: c.overdue ? "#dc2626" : undefined }}>{dayjs(v).format("DD/MM/YY")}</span> },
        { title: "Đơn vị", dataIndex: "unit_name", width: 220 },
        { title: "Hoạt động", dataIndex: "activity_name", width: 170, render: (v, c: any) => <Tag color={ACT_COLOR[c.activity]}>{v}</Tag> },
        { title: "Nội dung", dataIndex: "title", render: (v, c: any) => <div>{v}{c.result && <div className="muted" style={{ fontSize: 12 }}>Kết quả: {c.result}</div>}</div> },
        { title: "Trạng thái", dataIndex: "status", width: 130, render: (v) => <Tag color={v === "da_thuc_hien" ? "green" : v === "huy" ? "default" : "blue"}>{{ ke_hoach: "Kế hoạch", da_thuc_hien: "Đã thực hiện", huy: "Hủy" }[v as string]}</Tag> },
        { title: "", key: "a", width: 120, render: (_, c: any) => <Space>
          <Button size="small" onClick={() => { setEdit(c); form.setFieldsValue({ ...c, planned_date: dayjs(c.planned_date) }); }}>Sửa</Button>
          <Popconfirm title="Xóa hoạt động?" onConfirm={() => api.delete(`/am/care-plans/${c.id}`).then(load)}><Button size="small" danger>Xóa</Button></Popconfirm></Space> },
      ]} />
      <Modal open={!!edit} title={edit?.id ? "Cập nhật hoạt động chăm sóc" : "Thêm hoạt động chăm sóc"} onOk={save} onCancel={() => setEdit(null)} okText="Lưu">
        <Form form={form} layout="vertical">
          <Form.Item name="unit_id" label="Đơn vị" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={units.map((u: any) => ({ value: u.unit_id, label: u.name }))} /></Form.Item>
          <Space wrap>
            <Form.Item name="activity" label="Loại hoạt động"><Select style={{ width: 220 }} options={Object.entries(d.activities).map(([value, label]) => ({ value, label: label as string }))} /></Form.Item>
            <Form.Item name="planned_date" label="Ngày dự kiến" rules={[{ required: true }]}><DatePicker format="DD/MM/YYYY" /></Form.Item>
          </Space>
          <Form.Item name="title" label="Nội dung" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="service_code" label="Mã dịch vụ liên quan"><Input placeholder="VD: MEETING" /></Form.Item>
          <Form.Item name="status" label="Trạng thái"><Select options={[{ value: "ke_hoach", label: "Kế hoạch" }, { value: "da_thuc_hien", label: "Đã thực hiện" }, { value: "huy", label: "Hủy" }]} /></Form.Item>
          <Form.Item name="result" label="Kết quả"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="note" label="Ghi chú"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default function AMPortfolio() {
  const [period, setPeriod] = useState<string>();
  const [d, setD] = useState<any>();
  useEffect(() => { if (period) api.get("/am/portfolio", { params: { period } }).then((r) => setD(r.data)); }, [period]);
  const s = d?.summary;

  return (
    <>
      <PageHeader title="AM Intelligence" sub="Theo dõi đơn vị phụ trách · cơ hội phát triển dịch vụ · gia hạn · chăm sóc khai thác" extra={<PeriodSelect value={period} onChange={setPeriod} />} />
      {s && <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} lg={4}><Kpi title="Đơn vị phụ trách" value={s.units} /></Col>
        <Col xs={12} lg={5}><Kpi title="Doanh thu dịch vụ/tháng" value={money(s.monthly_revenue)} /></Col>
        <Col xs={12} lg={5}><Kpi title="Cơ hội dịch vụ mới" value={s.opportunities} color="#1d4ed8" foot={`Tiềm năng ~${money(s.potential_monthly)}/tháng`} /></Col>
        <Col xs={12} lg={5}><Kpi title="Cần gia hạn (≤ 60 ngày)" value={s.renewals} color="#ea580c" /></Col>
        <Col xs={24} lg={5}><Kpi title="Dịch vụ khai thác thấp" value={s.low_usage} color="#dc2626" foot="Mức sử dụng < 40%" /></Col>
      </Row>}
      {d && <Card size="small">
        <Tabs items={[
          { key: "opp", label: "Cơ hội phát triển dịch vụ", children: <Table size="small" rowKey={(r: any) => `${r.unit_id}-${r.service_code}`} dataSource={d.opportunities} pagination={{ pageSize: 12 }} columns={[
            { title: "Đơn vị", dataIndex: "unit_name", render: (v, r: any) => <Link to={`/units/${r.unit_id}`}>{v}</Link> },
            { title: "Dịch vụ đề xuất", dataIndex: "service_name" },
            { title: "Từ nhóm giải pháp", dataIndex: "solution", responsive: ["lg"] },
            { title: "Ưu tiên", dataIndex: "priority_level", render: (v) => <Tag color={SEVERITY[v].color}>{SEVERITY[v].text}</Tag> },
            { title: "Ước tính/tháng", dataIndex: "est_monthly", align: "right", render: (v) => money(v) },
            { title: "Căn cứ dữ liệu", dataIndex: "reason", responsive: ["xl"] },
          ]} /> },
          { key: "units", label: "Danh mục đơn vị", children: <Table size="small" rowKey="unit_id" dataSource={d.units} pagination={{ pageSize: 12 }} columns={[
            { title: "Đơn vị", dataIndex: "name", render: (v, r: any) => <Link to={`/units/${r.unit_id}`}>{v}</Link> },
            { title: "Địa bàn", dataIndex: "region", responsive: ["md"] },
            { title: "DTI", dataIndex: "dti", align: "right", sorter: (a: any, b: any) => (a.dti ?? 0) - (b.dti ?? 0), render: (v) => <Score v={v} /> },
            { title: "Mức", dataIndex: "level", render: (v) => <LevelTag level={v} /> },
            { title: "Dịch vụ", dataIndex: "active_services", align: "right" },
            { title: "Khai thác TB", dataIndex: "avg_usage", width: 140, render: (v) => <Progress percent={v} size="small" strokeColor={scoreColor(v)} /> },
            { title: "Doanh thu/tháng", dataIndex: "monthly_revenue", align: "right", sorter: (a: any, b: any) => a.monthly_revenue - b.monthly_revenue, render: (v) => money(v) },
            { title: "Cơ hội", dataIndex: "opportunities", align: "right", sorter: (a: any, b: any) => a.opportunities - b.opportunities },
          ]} /> },
          { key: "ren", label: `Gia hạn (${d.renewals.length})`, children: <Table size="small" rowKey={(r: any) => `${r.unit_id}-${r.service_name}`} dataSource={d.renewals} pagination={{ pageSize: 12 }} columns={[
            { title: "Đơn vị", dataIndex: "unit_name" }, { title: "Dịch vụ", dataIndex: "service_name" },
            { title: "Hết hạn", dataIndex: "end_date", render: (v) => new Date(v).toLocaleDateString("vi-VN") },
            { title: "Còn lại", dataIndex: "days_left", render: (v) => <Tag color={v < 0 ? "red" : v < 30 ? "orange" : "blue"}>{v < 0 ? `Quá ${-v} ngày` : `${v} ngày`}</Tag> },
            { title: "Phí/tháng", dataIndex: "monthly_fee", align: "right", render: (v) => money(v) },
          ]} /> },
          { key: "care", label: "Kế hoạch chăm sóc", children: <CarePlansTab units={d.units} /> },
          { key: "low", label: `Khai thác thấp (${d.care.length})`, children: <Table size="small" rowKey={(r: any) => `${r.unit_id}-${r.service_name}`} dataSource={d.care} pagination={{ pageSize: 12 }} columns={[
            { title: "Đơn vị", dataIndex: "unit_name" }, { title: "Dịch vụ khai thác thấp", dataIndex: "service_name" },
            { title: "Mức sử dụng", dataIndex: "usage_level", width: 200, render: (v) => <Progress percent={v} size="small" strokeColor={scoreColor(v)} /> },
          ]} /> },
          { key: "cov", label: "Tỷ lệ phủ dịch vụ", children: (
            <ResponsiveContainer width="100%" height={460}>
              <BarChart data={d.coverage} layout="vertical" margin={{ left: 30, right: 40 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
                <XAxis type="number" domain={[0, 100]} unit="%" fontSize={11} /><YAxis type="category" dataKey="name" width={300} fontSize={11} />
                <Tooltip formatter={(v: number, _n, p: any) => [`${v}% (${p.payload.using}/${p.payload.eligible})`, "Tỷ lệ phủ"]} />
                <Bar dataKey="rate" fill="#1d4ed8" radius={[0, 4, 4, 0]} label={{ position: "right", fontSize: 11, formatter: (v: number) => `${v}%` }} />
              </BarChart>
            </ResponsiveContainer>) },
        ]} />
      </Card>}
    </>
  );
}
