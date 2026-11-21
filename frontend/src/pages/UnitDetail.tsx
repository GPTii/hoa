import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Badge, Button, Card, Checkbox, Col, Descriptions, Empty, Form, InputNumber, Modal, Progress, Row, Space, Table, Tabs, Tag, Typography, message } from "antd";
import { useAuth } from "../auth";
import { UnitServicesTable } from "./Services";
import { CheckCircleTwoTone, CloseCircleTwoTone, EditOutlined, RiseOutlined } from "@ant-design/icons";
import {
  CartesianGrid, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { CHART_COLORS, Delta, LevelTag, PageHeader, PeriodSelect, Score, ScoreBar, SEVERITY, money, scoreColor } from "../components/common";

const SVC_STATUS: Record<string, [string, string]> = {
  dang_dung: ["success", "Đang dùng"], dung_thu: ["processing", "Dùng thử"], het_han: ["error", "Hết hạn"], ngung: ["default", "Ngừng"],
};
const SRC: Record<string, string> = { survey: "Khảo sát", tasks: "Nhiệm vụ (tự động)", infra: "Hạ tầng (tự động)", services: "Dịch vụ (tự động)" };
const Bool = ({ v }: { v: boolean }) => (v ? <CheckCircleTwoTone twoToneColor="#16a34a" /> : <CloseCircleTwoTone twoToneColor="#dc2626" />);

export default function UnitDetail() {
  const { id } = useParams();
  const [period, setPeriod] = useState<string>();
  const [d, setD] = useState<any>();
  const { user, can } = useAuth();
  const [infraOpen, setInfraOpen] = useState(false);
  const [infraForm] = Form.useForm();
  const load = () => { if (period) api.get(`/units/${id}`, { params: { period } }).then((r) => setD(r.data)); };
  useEffect(load, [id, period]);
  // Sở KH&CN cập nhật mọi đơn vị; đơn vị chỉ tự khai báo hạ tầng của chính mình
  const canEditInfra = can("unit.manage") || (can("unit.self_update") && user?.unit?.id === Number(id));
  const saveInfra = async () => {
    await api.put(`/units/${id}/infra`, await infraForm.validateFields());
    message.success("Đã lưu thông tin hạ tầng"); setInfraOpen(false); load();
  };
  if (!d) return <PageHeader title="Hồ sơ đơn vị" extra={<PeriodSelect value={period} onChange={setPeriod} />} />;
  const u = d.unit;

  return (
    <>
      <PageHeader title={u.name} sub={`${u.code} · ${u.category_name} · ${u.region_name}`} extra={<PeriodSelect value={period} onChange={setPeriod} />} />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card size="small" style={{ height: "100%" }}>
            {d.dti ? (
              <div style={{ textAlign: "center" }}>
                <Progress type="dashboard" percent={d.dti.score} strokeColor={scoreColor(d.dti.score)} size={180}
                  format={(p) => <div><div style={{ fontSize: 34, fontWeight: 700 }}>{p?.toFixed(1)}</div><div style={{ fontSize: 13 }} className="muted">DTI Score</div></div>} />
                <div style={{ marginTop: 4 }}><LevelTag level={d.dti.level} /></div>
                <Descriptions size="small" column={2} layout="vertical" style={{ marginTop: 16 }} items={[
                  { label: "Hạng toàn tỉnh", children: d.dti.rank_overall },
                  { label: "Hạng cùng loại", children: d.dti.rank_in_group },
                  { label: "So kỳ trước", children: <Delta v={d.dti.delta_prev} /> },
                  { label: "Dữ liệu đầy đủ", children: `${d.dti.completeness}%` },
                ]} />
                {d.cluster && (
                  <Alert style={{ textAlign: "left", marginTop: 8 }} type="info" showIcon icon={<RiseOutlined />}
                    message={<>Thuộc <b>{d.cluster.label}</b></>}
                    description={<>Dự báo kỳ tới (hồi quy xu hướng): <b>{d.cluster.forecast_next?.toFixed(1)}</b> điểm ({d.cluster.trend_slope >= 0 ? "+" : ""}{d.cluster.trend_slope?.toFixed(2)} điểm/kỳ)</>} />
                )}
              </div>
            ) : <Empty description="Chưa có kết quả đánh giá kỳ này" />}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title="Điểm trụ cột so với trung bình cùng loại hình" className="chart-card" style={{ height: "100%" }}>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={d.pillars} outerRadius="70%">
                <PolarGrid /><PolarAngleAxis dataKey="name" fontSize={11} /><PolarRadiusAxis domain={[0, 100]} angle={90} fontSize={10} />
                <Radar dataKey="score" name="Đơn vị" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.35} />
                <Radar dataKey="peer_avg" name="TB cùng loại" stroke={CHART_COLORS[2]} fill="none" strokeDasharray="4 3" />
                <Legend /><Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title="Diễn biến DTI qua các kỳ" className="chart-card" style={{ height: "100%" }}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={d.history} margin={{ left: -20, right: 10, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="period" fontSize={11} />
                <YAxis domain={[0, 100]} fontSize={11} /><Tooltip />
                <Line dataKey="score" name="DTI" stroke={CHART_COLORS[0]} strokeWidth={3} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24}>
          <Card size="small">
            <Tabs items={[
              {
                key: "rec", label: <Badge count={d.recommendations.length} offset={[12, 0]} color="#1d4ed8">Đề xuất cải thiện</Badge>,
                children: d.recommendations.length ? (
                  <Row gutter={[12, 12]}>
                    {d.recommendations.map((r: any) => (
                      <Col xs={24} md={12} xl={8} key={r.id}>
                        <Card size="small" style={{ height: "100%", borderLeft: `4px solid ${SEVERITY[r.priority_level].color === "red" ? "#dc2626" : SEVERITY[r.priority_level].color === "orange" ? "#ea580c" : "#1d4ed8"}` }}
                          title={<Tag color={SEVERITY[r.priority_level].color}>Ưu tiên {SEVERITY[r.priority_level].text.toLowerCase()}</Tag>}>
                          <div style={{ fontWeight: 600, marginBottom: 4 }}>{r.name}</div>
                          <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>Trụ cột: {r.pillar} · Điểm ưu tiên {r.priority_score} · ~{r.duration_months} tháng</Typography.Paragraph>
                          <div style={{ fontSize: 13 }}><b>Căn cứ:</b> {r.reason}</div>
                          <div style={{ fontSize: 13, marginTop: 4 }}><b>Hành động:</b> {r.actions}</div>
                          {r.missing_services?.length > 0 && <div style={{ marginTop: 6 }}>{r.missing_services.map((s: string) => <Tag key={s}>{s}</Tag>)}</div>}
                        </Card>
                      </Col>
                    ))}
                  </Row>
                ) : <Empty description="Không có đề xuất – các tiêu chí đều đạt khá" />,
              },
              {
                key: "crit", label: "Chi tiết tiêu chí",
                children: <Table size="small" rowKey="code" pagination={false} dataSource={d.criteria} columns={[
                  { title: "Mã", dataIndex: "code", width: 70 },
                  { title: "Tiêu chí", dataIndex: "name" },
                  { title: "Nguồn", dataIndex: "source", render: (v) => <Tag>{SRC[v]}</Tag>, responsive: ["lg"] },
                  { title: "Giá trị", dataIndex: "value", align: "right", render: (v, r: any) => v == null ? <span className="muted">Thiếu</span> : r.metric_type === "boolean" ? <Bool v={v >= 1} /> : `${v}${r.unit_label === "%" ? "%" : r.unit_label ? " " + r.unit_label : ""}` },
                  { title: "Mục tiêu", dataIndex: "target", align: "right", render: (v, r: any) => r.metric_type === "boolean" ? "Có" : `${v}${r.unit_label === "%" ? "%" : " " + (r.unit_label ?? "")}`, responsive: ["md"] },
                  { title: "Điểm", dataIndex: "score", width: 180, render: (v) => <Space style={{ width: "100%" }}><div style={{ width: 100 }}><ScoreBar v={v} /></div><Score v={v} /></Space> },
                ]} />,
              },
              {
                key: "svc", label: "Dịch vụ số đang sử dụng",
                children: <UnitServicesTable unitId={u.id} unitType={u.unit_type} services={d.services} onChanged={load} />,
              },
              {
                key: "infra", label: "Hạ tầng CNTT",
                children: d.infra ? <>{canEditInfra && <div style={{ marginBottom: 8 }}>
                  <Button icon={<EditOutlined />} onClick={() => { infraForm.setFieldsValue(d.infra); setInfraOpen(true); }}>
                    {can("unit.manage") ? "Cập nhật hạ tầng" : "Khai báo hạ tầng của đơn vị"}</Button>
                  <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>Số liệu băng thông, tường lửa, sao lưu được đồng bộ vào chỉ số DTI ở lần tính tiếp theo.</span></div>}
                <Descriptions bordered size="small" column={{ xs: 1, md: 3 }} items={[
                  { label: "Máy tính", children: d.infra.computers }, { label: "Máy chủ", children: d.infra.servers },
                  { label: "Băng thông", children: `${d.infra.internet_mbps} Mbps` }, { label: "Mạng LAN", children: <Bool v={d.infra.has_lan} /> },
                  { label: "Wifi", children: <Bool v={d.infra.has_wifi} /> }, { label: "Tường lửa", children: <Bool v={d.infra.has_firewall} /> },
                  { label: "Sao lưu định kỳ", children: <Bool v={d.infra.has_backup} /> }, { label: "Camera", children: <Bool v={d.infra.has_camera} /> },
                  ...(u.unit_type === "giao_duc" ? [{ label: "Phòng học thông minh", children: d.infra.smart_classrooms }] : []),
                ]} /></> : <Empty />,
              },
              {
                key: "info", label: "Thông tin đơn vị",
                children: <Descriptions bordered size="small" column={{ xs: 1, md: 2 }} items={[
                  { label: "Mã đơn vị", children: u.code }, { label: "Phân loại", children: u.category_name },
                  { label: "Cấp quản lý", children: u.level === "tinh" ? "Cấp tỉnh" : "Cấp xã" }, { label: "Địa bàn", children: u.region_name },
                  { label: "Người đứng đầu", children: u.head_name }, { label: "Điện thoại", children: u.phone },
                  { label: "Email", children: u.email }, { label: "Số CBCCVC/GV", children: u.staff_count },
                  ...(u.student_count ? [{ label: "Số học sinh", children: u.student_count }] : []),
                ]} />,
              },
            ]} />
          </Card>
        </Col>
      </Row>
      <Modal open={infraOpen} title="Khai báo hạ tầng CNTT" onOk={saveInfra} onCancel={() => setInfraOpen(false)} okText="Lưu">
        <Form form={infraForm} layout="vertical">
          <Row gutter={12}>
            <Col span={8}><Form.Item name="computers" label="Số máy tính"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="servers" label="Số máy chủ"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="internet_mbps" label="Băng thông (Mbps)"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="smart_classrooms" label="Phòng học thông minh"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item></Col>
          </Row>
          {[["has_lan", "Mạng LAN"], ["has_wifi", "Wifi"], ["has_firewall", "Tường lửa, phòng chống mã độc"], ["has_backup", "Sao lưu dữ liệu định kỳ"], ["has_camera", "Camera an ninh"]].map(([k, l]) =>
            <Form.Item key={k} name={k} valuePropName="checked" style={{ marginBottom: 4 }}><Checkbox>{l}</Checkbox></Form.Item>)}
        </Form>
      </Modal>
    </>
  );
}
