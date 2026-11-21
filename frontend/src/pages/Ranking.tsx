import { useEffect, useState } from "react";
import { Card, Empty, Input, Select, Space, Table, Tabs, Tag } from "antd";
import { Link } from "react-router-dom";
import {
  CartesianGrid, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { CHART_COLORS, Delta, LEVEL_ORDER, LevelTag, PageHeader, PeriodSelect, PILLAR_NAMES, Score, ScoreBar, UNIT_TYPE, useRegions } from "../components/common";

function UnitRanking({ period }: { period?: string }) {
  const regions = useRegions();
  const [f, setF] = useState<any>({ page: 1, size: 20 });
  const [data, setData] = useState<any>({ total: 0, items: [] });
  useEffect(() => { if (period) api.get("/analytics/ranking", { params: { ...f, period } }).then((r) => setData(r.data)); }, [f, period]);
  return (
    <>
      <Space wrap style={{ marginBottom: 12 }}>
        <Input.Search allowClear placeholder="Tìm đơn vị" style={{ width: 220 }} onSearch={(q) => setF({ ...f, q, page: 1 })} />
        <Select allowClear placeholder="Loại hình" style={{ width: 180 }} onChange={(v) => setF({ ...f, unit_type: v, page: 1 })}
          options={Object.entries(UNIT_TYPE).map(([value, label]) => ({ value, label }))} />
        <Select allowClear placeholder="Mức độ" style={{ width: 150 }} onChange={(v) => setF({ ...f, level: v, page: 1 })} options={LEVEL_ORDER.map((l) => ({ value: l, label: l }))} />
        <Select allowClear showSearch optionFilterProp="label" placeholder="Địa bàn" style={{ width: 200 }} onChange={(v) => setF({ ...f, region_id: v, page: 1 })}
          options={regions.map((r) => ({ value: r.id, label: r.name }))} />
      </Space>
      <Table rowKey="unit_id" size="small" dataSource={data.items} scroll={{ x: 1100 }}
        pagination={{ current: f.page, pageSize: f.size, total: data.total, onChange: (page, size) => setF({ ...f, page, size }) }}
        columns={[
          { title: "Hạng", dataIndex: "rank", width: 60, fixed: "left" },
          { title: "Đơn vị", dataIndex: "name", fixed: "left", width: 240, render: (v, r: any) => <Link to={`/units/${r.unit_id}`}>{v}</Link> },
          { title: "Địa bàn", dataIndex: "region", width: 150 },
          { title: "DTI", dataIndex: "score", width: 70, align: "right", render: (v) => <Score v={v} /> },
          { title: "Mức", dataIndex: "level", width: 100, render: (v) => <LevelTag level={v} /> },
          { title: "±", dataIndex: "delta_prev", width: 70, align: "right", render: (v) => <Delta v={v} /> },
          ...Object.entries(PILLAR_NAMES).map(([k, n]) => ({ title: n, key: k, width: 90, render: (_: any, r: any) => <ScoreBar v={r.pillars[k]} /> })),
          { title: "Nhóm (ML)", dataIndex: "cluster", width: 190, render: (v) => v && <Tag>{v}</Tag> },
        ]} />
    </>
  );
}

function RegionRanking({ period }: { period?: string }) {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { if (period) api.get("/analytics/regions", { params: { period } }).then((r) => setRows(r.data)); }, [period]);
  return (
    <Table rowKey="region_id" size="small" dataSource={rows} pagination={{ pageSize: 50 }} scroll={{ x: 1100 }} columns={[
      { title: "Hạng", dataIndex: "rank", width: 60 },
      { title: "Địa bàn", dataIndex: "name", width: 180 },
      { title: "Số ĐV", dataIndex: "count", width: 70, align: "right" },
      { title: "DTI TB", dataIndex: "avg", width: 80, align: "right", sorter: (a: any, b: any) => a.avg - b.avg, render: (v) => <Score v={v} /> },
      { title: "Hành chính", dataIndex: "admin_avg", width: 95, align: "right", render: (v) => <Score v={v} /> },
      { title: "Giáo dục", dataIndex: "edu_avg", width: 90, align: "right", render: (v) => <Score v={v} /> },
      { title: "Thấp–Cao", key: "mm", width: 110, render: (_, r: any) => <span className="num">{r.min.toFixed(0)} – {r.max.toFixed(0)}</span> },
      { title: "ĐV < 40đ", dataIndex: "low_count", width: 80, align: "right", render: (v) => v ? <Tag color="red">{v}</Tag> : 0 },
      ...Object.entries(PILLAR_NAMES).map(([k, n]) => ({ title: n, key: k, width: 90, render: (_: any, r: any) => <ScoreBar v={r.pillars[k]} /> })),
    ]} />
  );
}

function Compare({ period }: { period?: string }) {
  const [opts, setOpts] = useState<any[]>([]);
  const [ids, setIds] = useState<number[]>([]);
  const [data, setData] = useState<any[]>([]);
  useEffect(() => { api.get("/analytics/ranking", { params: { period, size: 500 } }).then((r) => setOpts(r.data.items)); }, [period]);
  useEffect(() => {
    if (!ids.length || !period) return setData([]);
    api.get("/analytics/compare", { params: { unit_ids: ids.join(","), period } }).then((r) => setData(r.data));
  }, [ids, period]);
  const radar = Object.entries(PILLAR_NAMES).map(([k, n]) => ({ name: n, ...Object.fromEntries(data.map((d) => [d.name, d.pillars[k]])) }));
  const periods = data[0]?.history.map((h: any) => h.period) ?? [];
  const line = periods.map((p: string) => ({ period: p, ...Object.fromEntries(data.map((d) => [d.name, d.history.find((h: any) => h.period === p)?.score])) }));
  return (
    <>
      <Select mode="multiple" maxCount={5} style={{ width: "100%", marginBottom: 16 }} placeholder="Chọn tối đa 5 đơn vị để so sánh" showSearch optionFilterProp="label"
        value={ids} onChange={setIds} options={opts.map((o) => ({ value: o.unit_id, label: `${o.name} (${o.score.toFixed(1)})` }))} />
      {data.length ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: 16 }}>
          <Card size="small" title="So sánh theo trụ cột"><ResponsiveContainer width="100%" height={340}>
            <RadarChart data={radar} outerRadius="70%"><PolarGrid /><PolarAngleAxis dataKey="name" fontSize={11} /><PolarRadiusAxis domain={[0, 100]} angle={90} fontSize={10} />
              {data.map((d, i) => <Radar key={d.name} dataKey={d.name} stroke={CHART_COLORS[i]} fill={CHART_COLORS[i]} fillOpacity={0.12} />)}
              <Legend /><Tooltip /></RadarChart></ResponsiveContainer></Card>
          <Card size="small" title="Diễn biến DTI"><ResponsiveContainer width="100%" height={340}>
            <LineChart data={line} margin={{ left: -20, right: 10 }}><CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="period" fontSize={11} /><YAxis domain={[0, 100]} fontSize={11} />
              {data.map((d, i) => <Line key={d.name} dataKey={d.name} stroke={CHART_COLORS[i]} strokeWidth={2} />)}<Legend /><Tooltip /></LineChart></ResponsiveContainer></Card>
        </div>
      ) : <Empty description="Chọn đơn vị để so sánh" />}
    </>
  );
}

export default function Ranking() {
  const [period, setPeriod] = useState<string>();
  return (
    <>
      <PageHeader title="Xếp hạng & so sánh" sub="Bảng xếp hạng DTI theo đơn vị, theo xã/phường và so sánh nhiều đơn vị" extra={<PeriodSelect value={period} onChange={setPeriod} />} />
      <Card size="small">
        <Tabs destroyInactiveTabPane items={[
          { key: "u", label: "Theo đơn vị", children: <UnitRanking period={period} /> },
          { key: "r", label: "Theo xã, phường", children: <RegionRanking period={period} /> },
          { key: "c", label: "So sánh đơn vị", children: <Compare period={period} /> },
        ]} />
      </Card>
    </>
  );
}
