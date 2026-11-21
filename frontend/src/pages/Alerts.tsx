import { useEffect, useState } from "react";
import { Card, Col, Progress, Row, Select, Space, Table, Tag } from "antd";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ALERT_TYPES, Delta, Kpi, LevelTag, PageHeader, PeriodSelect, Score, SEVERITY, UNIT_TYPE } from "../components/common";

export default function Alerts() {
  const [period, setPeriod] = useState<string>();
  const [f, setF] = useState<any>({ page: 1, size: 15 });
  const [data, setData] = useState<any>({ total: 0, items: [], counts: {} });
  const [prio, setPrio] = useState<any[]>([]);
  const [unitType, setUnitType] = useState<string>();

  useEffect(() => { if (period) api.get("/analytics/alerts", { params: { ...f, period, unit_type: unitType } }).then((r) => setData(r.data)); }, [f, period, unitType]);
  useEffect(() => { if (period) api.get("/analytics/priority", { params: { period, limit: 15, unit_type: unitType } }).then((r) => setPrio(r.data)); }, [period, unitType]);

  return (
    <>
      <PageHeader title="Cảnh báo & đơn vị ưu tiên" sub="Phát hiện tự động từ kết quả đánh giá, biến động điểm, nhiệm vụ trễ hạn và độ đầy đủ dữ liệu"
        extra={<>
          <Select allowClear placeholder="Loại hình" style={{ width: 180 }} value={unitType} onChange={setUnitType}
            options={Object.entries(UNIT_TYPE).map(([value, label]) => ({ value, label }))} />
          <PeriodSelect value={period} onChange={setPeriod} />
        </>} />
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {Object.entries(ALERT_TYPES).map(([k, n]) => (
          <Col xs={12} md={8} xl={4} key={k}>
            <div onClick={() => setF({ ...f, alert_type: f.alert_type === k ? undefined : k, page: 1 })} style={{ cursor: "pointer", outline: f.alert_type === k ? "2px solid #1d4ed8" : "none", borderRadius: 8 }}>
              <Kpi title={n} value={data.counts[k] ?? 0} color={k === "LOW_SCORE" || k === "OVERDUE_TASK" ? "#dc2626" : undefined} />
            </div>
          </Col>
        ))}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card size="small" title="Danh sách đơn vị cần ưu tiên" extra={<span className="muted" style={{ fontSize: 12 }}>Chỉ số ưu tiên 0–100</span>}>
            <Table size="small" rowKey="unit_id" pagination={false} dataSource={prio} columns={[
              { title: "#", key: "i", width: 36, render: (_, __, i) => i + 1 },
              { title: "Đơn vị", dataIndex: "name", render: (v, r: any) => <div><Link to={`/units/${r.unit_id}`}>{v}</Link><div className="muted" style={{ fontSize: 12 }}>{r.reasons}</div></div> },
              { title: "DTI", dataIndex: "score", align: "right", render: (v) => <Score v={v} /> },
              { title: "Ưu tiên", dataIndex: "priority_index", width: 110, render: (v) => <Progress percent={v} size="small" strokeColor="#dc2626" format={(p) => p?.toFixed(0)} /> },
            ]} />
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card size="small" title={`Cảnh báo${f.alert_type ? ` – ${ALERT_TYPES[f.alert_type]}` : ""}`}
            extra={<Space><Select allowClear placeholder="Mức độ" style={{ width: 130 }} onChange={(v) => setF({ ...f, severity: v, page: 1 })}
              options={Object.entries(SEVERITY).map(([value, s]) => ({ value, label: s.text }))} /></Space>}>
            <Table size="small" rowKey="id" dataSource={data.items}
              pagination={{ current: f.page, pageSize: f.size, total: data.total, onChange: (page, size) => setF({ ...f, page, size }) }}
              columns={[
                { title: "Mức", dataIndex: "severity", width: 100, render: (v) => <Tag color={SEVERITY[v].color}>{SEVERITY[v].text}</Tag> },
                { title: "Loại", dataIndex: "alert_type", width: 140, render: (v) => ALERT_TYPES[v] },
                { title: "Đơn vị", dataIndex: "unit_name", render: (v, r: any) => <div><Link to={`/units/${r.unit_id}`}>{v}</Link><div className="muted" style={{ fontSize: 12 }}>{r.region}</div></div> },
                { title: "Nội dung", dataIndex: "message" },
              ]} />
          </Card>
        </Col>
      </Row>
    </>
  );
}
