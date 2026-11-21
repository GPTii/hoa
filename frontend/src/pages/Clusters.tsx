import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, InputNumber, Row, Space, Table, Tag } from "antd";
import { ExperimentOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import {
  CartesianGrid, Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Scatter, Bar, BarChart,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import { CHART_COLORS, PageHeader, PeriodSelect, PILLAR_NAMES, Score } from "../components/common";

export default function Clusters() {
  const { can } = useAuth();
  const [period, setPeriod] = useState<string>();
  const [d, setD] = useState<any>();
  const [k, setK] = useState(4);
  const [sil, setSil] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [evalRes, setEvalRes] = useState<any>();
  const load = () => {
    if (!period) return;
    api.get("/analytics/clusters", { params: { period } }).then((r) => setD(r.data));
    api.get("/data/ml/evaluate", { params: { period } }).then((r) => setEvalRes(r.data));
  };
  useEffect(() => { load(); }, [period]);
  const run = async () => {
    setRunning(true);
    try { const r = await api.post("/data/ml/cluster", null, { params: { period, k } }); setSil(r.data.silhouette); load(); } finally { setRunning(false); }
  };
  const radar = Object.entries(PILLAR_NAMES).map(([c, n]) => ({ name: n, ...Object.fromEntries((d?.profile ?? []).map((p: any) => [p.label, p.pillars[c]])) }));

  return (
    <>
      <PageHeader title="Phân cụm & dự báo (Machine Learning)" sub="K-Means trên vector 7 điểm trụ cột · Hồi quy tuyến tính dự báo DTI kỳ kế tiếp"
        extra={<>
          {can("ml.run") && <Space><span>Số cụm k</span><InputNumber min={2} max={6} value={k} onChange={(v) => setK(v ?? 4)} />
            <Button icon={<ExperimentOutlined />} loading={running} onClick={run}>Chạy lại mô hình</Button></Space>}
          <PeriodSelect value={period} onChange={setPeriod} />
        </>} />
      {sil != null && <Alert style={{ marginBottom: 12 }} showIcon type="success" message={`Đã phân cụm lại. Silhouette score = ${sil} (càng gần 1 càng tách biệt)`} />}
      {evalRes && <Card size="small" title="Đánh giá mô hình" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col xs={24} lg={12}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Chọn số cụm k (silhouette – càng cao càng tách biệt)</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={evalRes.clustering} margin={{ left: -20 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="k" fontSize={11} tickFormatter={(k) => `k=${k}`} /><YAxis fontSize={11} /><Tooltip />
                <Bar dataKey="silhouette" fill="#1d4ed8" radius={[3, 3, 0, 0]} /></BarChart>
            </ResponsiveContainer>
            <div className="muted" style={{ fontSize: 12 }}>k tốt nhất theo silhouette: <b>{evalRes.best_k}</b>. Hệ thống dùng k = 4 mặc định để có 4 nhóm dễ diễn giải cho quản lý (dẫn đầu / khá / trung bình / yếu); có thể chạy lại với k khác.</div>
          </Col>
          <Col xs={24} lg={12}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Kiểm định dự báo (backtest kỳ {evalRes.period}, {evalRes.forecast?.units} đơn vị)</div>
            {evalRes.forecast && <Table size="small" pagination={false} rowKey="m" dataSource={[
              { m: "Hồi quy tuyến tính (hệ thống)", ...evalRes.forecast.linear }, { m: "Cơ sở: giữ nguyên kỳ trước", ...evalRes.forecast.naive }]} columns={[
              { title: "Mô hình", dataIndex: "m" }, { title: "MAE", dataIndex: "mae" }, { title: "RMSE", dataIndex: "rmse" }, { title: "MAPE (%)", dataIndex: "mape" }]} />}
            {evalRes.forecast && <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Sai số tuyệt đối trung bình giảm <b>{evalRes.forecast.improvement_pct}%</b> so với mô hình cơ sở.</div>}
          </Col>
        </Row>
      </Card>}
      <Row gutter={[16, 16]}>
        {d?.profile.map((p: any, i: number) => (
          <Col xs={12} lg={6} key={p.cluster}>
            <Card size="small" style={{ borderTop: `4px solid ${CHART_COLORS[i]}` }}>
              <div style={{ fontWeight: 600 }}>{p.label}</div>
              <div style={{ fontSize: 26, fontWeight: 700 }}>{p.size} <span className="muted" style={{ fontSize: 14 }}>đơn vị</span></div>
              <div className="muted">DTI TB: <Score v={p.avg} /></div>
            </Card>
          </Col>
        ))}
        <Col xs={24} lg={11}>
          <Card size="small" title="Hồ sơ đặc trưng từng cụm (tâm cụm)">
            <ResponsiveContainer width="100%" height={360}>
              <RadarChart data={radar} outerRadius="70%"><PolarGrid /><PolarAngleAxis dataKey="name" fontSize={11} /><PolarRadiusAxis domain={[0, 100]} angle={90} fontSize={10} />
                {d?.profile.map((p: any, i: number) => <Radar key={p.label} dataKey={p.label} stroke={CHART_COLORS[i]} fill={CHART_COLORS[i]} fillOpacity={0.1} />)}
                <Legend /><Tooltip /></RadarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={13}>
          <Card size="small" title="DTI hiện tại và dự báo kỳ tới">
            <ResponsiveContainer width="100%" height={360}>
              <ScatterChart margin={{ left: -10, right: 10, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" dataKey="score" name="DTI hiện tại" domain={[0, 100]} fontSize={11} label={{ value: "DTI hiện tại", position: "insideBottom", offset: -2, fontSize: 11 }} />
                <YAxis type="number" dataKey="forecast_next" name="Dự báo" domain={[0, 100]} fontSize={11} />
                <ZAxis range={[30, 30]} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ payload }) => payload?.[0] ? (
                  <Card size="small"><b>{(payload[0].payload as any).name}</b><div>DTI: {(payload[0].payload as any).score} → dự báo {(payload[0].payload as any).forecast_next}</div></Card>) : null} />
                <Legend />
                {d?.profile.map((p: any, i: number) => <Scatter key={p.label} name={p.label} data={d.units.filter((u: any) => u.cluster === p.cluster)} fill={CHART_COLORS[i]} />)}
              </ScatterChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24}>
          <Card size="small" title="Đơn vị theo cụm">
            <Table size="small" rowKey="unit_id" dataSource={d?.units ?? []} pagination={{ pageSize: 10 }} columns={[
              { title: "Đơn vị", dataIndex: "name", render: (v, r: any) => <Link to={`/units/${r.unit_id}`}>{v}</Link> },
              { title: "Địa bàn", dataIndex: "region", responsive: ["md"] },
              { title: "Cụm", dataIndex: "label", filters: d?.profile.map((p: any) => ({ text: p.label, value: p.label })), onFilter: (v, r: any) => r.label === v, render: (v, r: any) => <Tag color={CHART_COLORS[r.cluster]}>{v}</Tag> },
              { title: "DTI", dataIndex: "score", align: "right", sorter: (a: any, b: any) => a.score - b.score, render: (v) => <Score v={v} /> },
              { title: "Dự báo kỳ tới", dataIndex: "forecast_next", align: "right", render: (v) => <Score v={v} /> },
              { title: "Xu hướng/kỳ", dataIndex: "trend_slope", align: "right", sorter: (a: any, b: any) => a.trend_slope - b.trend_slope, render: (v) => <span style={{ color: v >= 0 ? "#16a34a" : "#dc2626" }}>{v >= 0 ? "+" : ""}{v?.toFixed(2)}</span> },
            ]} />
          </Card>
        </Col>
      </Row>
    </>
  );
}
