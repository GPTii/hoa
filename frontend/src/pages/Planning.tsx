import { useEffect, useState } from "react";
import { Card, Col, Drawer, Row, Segmented, Steps, Table, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import { useNavigate } from "react-router-dom";
import { Button } from "antd";
import { FileAddOutlined } from "@ant-design/icons";
import { CreatePlanModal } from "./Plans";
import { PageHeader, PeriodSelect, SEVERITY } from "../components/common";

const COST: Record<string, string> = { thap: "Thấp", trung_binh: "Trung bình", cao: "Cao" };

export default function Planning() {
  const [period, setPeriod] = useState<string>();
  const [unitType, setUnitType] = useState("");
  const [d, setD] = useState<any>();
  const [sel, setSel] = useState<any>();
  const [units, setUnits] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const { can } = useAuth();
  const nav = useNavigate();
  useEffect(() => { if (period) api.get("/analytics/planning", { params: { period, unit_type: unitType || undefined } }).then((r) => setD(r.data)); }, [period, unitType]);
  const open = (g: any) => { setSel(g); api.get(`/analytics/planning/${g.id}/units`, { params: { period } }).then((r) => setUnits(r.data)); };

  return (
    <>
      <PageHeader title="Hỗ trợ hoạch định chuyển đổi số" sub="Từ hiện trạng → vấn đề → mức ưu tiên → nhóm giải pháp tham khảo"
        extra={<>
          <Segmented value={unitType} onChange={(v) => setUnitType(v as string)} options={[{ label: "Tất cả", value: "" }, { label: "Hành chính", value: "hanh_chinh" }, { label: "Giáo dục", value: "giao_duc" }]} />
          <PeriodSelect value={period} onChange={setPeriod} />
          <Button onClick={() => nav("/plans")}>Kế hoạch đã lập</Button>
          {can("plan.manage") && <Button type="primary" icon={<FileAddOutlined />} disabled={!d?.groups?.length} onClick={() => setCreating(true)}>Lập kế hoạch từ đề xuất</Button>}
        </>} />
      {creating && d && <CreatePlanModal groups={d.groups} onClose={() => setCreating(false)} />}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Steps size="small" current={4} items={[
          { title: "Đánh giá hiện trạng", description: "DTI & 7 trụ cột" }, { title: "Xác định vấn đề", description: "Tiêu chí ≤ 60 điểm" },
          { title: "Mức độ ưu tiên", description: "Độ thiếu hụt × trọng số" }, { title: "Đề xuất nhóm giải pháp", description: "Luật kích hoạt" },
          { title: "Hỗ trợ hoạch định", description: "Kế hoạch theo nhóm/đơn vị" },
        ]} />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card size="small" title="Mức độ trụ cột trong phạm vi quản lý" className="chart-card">
            <ResponsiveContainer width="100%" height={330}>
              <BarChart data={d?.pillars ?? []} layout="vertical" margin={{ left: 20, right: 20 }} stackOffset="expand">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
                <XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} fontSize={11} />
                <YAxis type="category" dataKey="name" width={150} fontSize={11} />
                <Tooltip /><Legend />
                <Bar dataKey="weak" name="Yếu (<30)" stackId="a" fill="#dc2626" />
                <Bar dataKey="medium" name="Trung bình (30–50)" stackId="a" fill="#f59e0b" />
                <Bar dataKey="good" name="Khá trở lên (≥50)" stackId="a" fill="#16a34a" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Card size="small" title="Nhóm giải pháp được đề xuất (bấm để xem đơn vị cần triển khai)">
            <Table size="small" rowKey="id" dataSource={d?.groups ?? []} pagination={false} onRow={(g) => ({ onClick: () => open(g), style: { cursor: "pointer" } })} columns={[
              { title: "Nhóm giải pháp", dataIndex: "name", render: (v, r: any) => <div><b>{v}</b><div className="muted" style={{ fontSize: 12 }}>{r.pillar}</div></div> },
              { title: "Số ĐV", dataIndex: "unit_count", align: "right" },
              { title: "Ưu tiên cao", dataIndex: "high_count", align: "right", render: (v) => v ? <Tag color="red">{v}</Tag> : 0 },
              { title: "Điểm ưu tiên TB", dataIndex: "avg_priority", align: "right" },
              { title: "Chi phí", dataIndex: "cost_level", render: (v) => COST[v], responsive: ["md"] },
              { title: "Thời gian", dataIndex: "duration_months", render: (v) => `${v} tháng`, responsive: ["md"] },
            ]} />
          </Card>
        </Col>
      </Row>
      <Drawer width={720} open={!!sel} onClose={() => setSel(null)} title={sel?.name}>
        {sel && <>
          <Typography.Paragraph><b>Hành động gợi ý:</b> {sel.actions}</Typography.Paragraph>
          {sel.service_codes?.length > 0 && <Typography.Paragraph><b>Dịch vụ/giải pháp liên quan:</b> {sel.service_codes.map((s: string) => <Tag key={s}>{s}</Tag>)}</Typography.Paragraph>}
          <Table size="small" rowKey="unit_id" dataSource={units} pagination={{ pageSize: 15 }} columns={[
            { title: "Đơn vị", dataIndex: "name", render: (v, r: any) => <div><Link to={`/units/${r.unit_id}`}>{v}</Link><div className="muted" style={{ fontSize: 12 }}>{r.region}</div></div> },
            { title: "Ưu tiên", dataIndex: "priority_level", render: (v) => <Tag color={SEVERITY[v].color}>{SEVERITY[v].text}</Tag> },
            { title: "Điểm", dataIndex: "priority_score", align: "right" },
            { title: "Căn cứ", dataIndex: "reason" },
          ]} />
        </>}
      </Drawer>
    </>
  );
}
