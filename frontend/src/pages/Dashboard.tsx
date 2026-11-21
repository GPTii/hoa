import { useEffect, useState } from "react";
import { Card, Col, Empty, List, Row, Segmented, Select, Spin, Table, Tag } from "antd";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar,
  RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import { useSysConfig } from "../sysconfig";
import {
  CHART_COLORS, Delta, Kpi, LEVEL_COLORS, LevelTag, PageHeader, PeriodSelect, Score, scoreColor, useRegions,
} from "../components/common";

export default function Dashboard() {
  const { cfg } = useSysConfig();
  const { user } = useAuth();
  const [period, setPeriod] = useState<string>();
  const [unitType, setUnitType] = useState<string>("");
  const [regionId, setRegionId] = useState<number>();
  const [d, setD] = useState<any>();
  const regions = useRegions();
  const wide = user?.role.data_scope === "all";

  useEffect(() => {
    if (!period) return;
    api.get("/analytics/overview", { params: { period, unit_type: unitType || undefined, region_id: regionId } }).then((r) => setD(r.data));
  }, [period, unitType, regionId]);

  if (!d) return <PageHeader title="Tổng quan chuyển đổi số" extra={<PeriodSelect value={period} onChange={setPeriod} />} />;
  const k = d.kpi;
  const byCat = [...d.by_category].sort((a: any, b: any) => b.avg - a.avg);
  const tasksDoneRate =d.tasks.total ? Math.round((d.tasks.hoan_thanh * 100) / d.tasks.total) : 0;

  return (
    <>
      <PageHeader title="Tổng quan chuyển đổi số"
        sub={<>{`Kỳ ${d.period}${d.prev_period ? ` · so sánh với ${d.prev_period}` : ""} · ${user?.unit?.name ?? `Toàn ${cfg.province_label || "tỉnh"}`}`}{" "}
          {d.published ? <Tag color="green">Kết quả chính thức · QĐ {d.publish_decision}</Tag> : <Tag color="orange">Tạm tính – chưa công bố</Tag>}</>}
        extra={<>
          <Segmented value={unitType} onChange={(v) => setUnitType(v as string)}
            options={[{ label: "Tất cả", value: "" }, { label: "Hành chính", value: "hanh_chinh" }, { label: "Giáo dục", value: "giao_duc" }]} />
          {wide && <Select allowClear placeholder="Mọi xã/phường" style={{ width: 200 }} value={regionId} onChange={setRegionId} showSearch optionFilterProp="label"
            options={regions.filter((r) => r.type !== "tinh").map((r) => ({ value: r.id, label: r.name }))} />}
          <PeriodSelect value={period} onChange={setPeriod} />
        </>} />

      <Row gutter={[16, 16]}>
        <Col xs={12} lg={4}><Kpi title="Đơn vị được đánh giá" value={k.units} /></Col>
        <Col xs={12} lg={5}><Kpi title="DTI trung bình" value={k.avg_dti.toFixed(1)} suffix="/100" color={scoreColor(k.avg_dti)}
          foot={<>So kỳ trước: <Delta v={k.delta_avg} /></>} /></Col>
        <Col xs={12} lg={5}><Kpi title="Cao nhất / thấp nhất" value={<><Score v={k.max} size={26} /> <span className="muted">/</span> <Score v={k.min} size={26} /></>} /></Col>
        <Col xs={12} lg={5}><Kpi title="Cảnh báo mức cao" value={k.alerts_high} color="#dc2626" foot={`Tổng ${k.alerts_total} cảnh báo · ${k.priority_units} đơn vị DTI < 40`} /></Col>
        <Col xs={24} lg={5}><Kpi title="Nhiệm vụ hoàn thành" value={`${tasksDoneRate}%`} color="#16a34a"
          foot={<>{d.tasks.hoan_thanh}/{d.tasks.total} lượt · <span style={{ color: "#dc2626" }}>{d.tasks.qua_han} quá hạn</span></>} /></Col>

        <Col xs={24} lg={14}>
          <Card title="Xu hướng DTI trung bình theo kỳ" size="small" className="chart-card">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={d.trend} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="period" fontSize={12} /><YAxis domain={[0, 100]} fontSize={12} />
                <Tooltip formatter={(v: number) => v.toFixed(1)} /><Legend />
                <Line dataKey="all" name="Chung" stroke={CHART_COLORS[0]} strokeWidth={3} dot={{ r: 3 }} />
                <Line dataKey="hanh_chinh" name="Hành chính" stroke={CHART_COLORS[1]} strokeDasharray="5 4" dot={false} />
                <Line dataKey="giao_duc" name="Giáo dục" stroke={CHART_COLORS[2]} strokeDasharray="5 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Điểm trung bình theo trụ cột" size="small" className="chart-card">
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={d.pillars} outerRadius="62%">
                <PolarGrid /><PolarAngleAxis dataKey="name" fontSize={11} /><PolarRadiusAxis domain={[0, 100]} fontSize={10} angle={90} />
                <Radar dataKey="avg" name="Điểm TB" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.3} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Phân loại mức độ chuyển đổi số" size="small" className="chart-card">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={d.levels} layout="vertical" margin={{ left: 10, right: 30 }}>
                <XAxis type="number" hide /><YAxis type="category" dataKey="level" width={80} fontSize={12} />
                <Tooltip /><Bar dataKey="count" name="Số đơn vị" radius={[0, 4, 4, 0]} label={{ position: "right", fontSize: 12 }}>
                  {d.levels.map((l: any) => <Cell key={l.level} fill={LEVEL_COLORS[l.level]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Phân bố điểm DTI" size="small" className="chart-card">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={d.histogram} margin={{ left: -20, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="bin" fontSize={10} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip />
                <Bar dataKey="count" name="Số đơn vị" radius={[4, 4, 0, 0]}>
                  {d.histogram.map((h: any, i: number) => <Cell key={i} fill={scoreColor(i * 10 + 5)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="DTI theo loại hình đơn vị" size="small" className="chart-card">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={byCat} layout="vertical" margin={{ left: 10, right: 30 }}>
                <XAxis type="number" domain={[0, 100]} hide /><YAxis type="category" dataKey="name" width={130} fontSize={11} />
                <Tooltip formatter={(v: number) => v.toFixed(1)} />
                <Bar dataKey="avg" name="DTI TB" radius={[0, 4, 4, 0]} label={{ position: "right", fontSize: 11, formatter: (v: number) => v.toFixed(1) }}>
                  {byCat.map((c: any) => <Cell key={c.category} fill={scoreColor(c.avg)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {d.regions.length > 1 && (
          <Col xs={24}>
            <Card title="DTI trung bình theo xã, phường" size="small" className="chart-card" extra={<Link to="/ranking">Xem chi tiết</Link>}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={d.regions} margin={{ left: -20, right: 10, bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="name" angle={-55} textAnchor="end" interval={0} fontSize={10} height={70} />
                  <YAxis domain={[0, 100]} fontSize={11} /><Tooltip formatter={(v: number) => v.toFixed(1)} />
                  <Bar dataKey="avg" name="DTI TB" radius={[3, 3, 0, 0]}>{d.regions.map((r: any) => <Cell key={r.id} fill={scoreColor(r.avg)} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}

        {[["Top đơn vị dẫn đầu", d.top], ["Đơn vị cần quan tâm", d.bottom]].map(([title, rows]: any) => (
          <Col xs={24} lg={12} key={title}>
            <Card title={title} size="small">
              {rows.length ? <Table size="small" pagination={false} rowKey="id" dataSource={rows} columns={[
                { title: "Đơn vị", dataIndex: "name", render: (v, r: any) => <Link to={`/units/${r.id}`}>{v}</Link> },
                { title: "Địa bàn", dataIndex: "region", responsive: ["md"] },
                { title: "DTI", dataIndex: "score", align: "right", render: (v) => <Score v={v} /> },
                { title: "Mức", dataIndex: "level", render: (v) => <LevelTag level={v} /> },
                { title: "± kỳ trước", dataIndex: "delta_prev", align: "right", render: (v) => <Delta v={v} /> },
              ]} /> : <Empty />}
            </Card>
          </Col>
        ))}
      </Row>
    </>
  );
}
