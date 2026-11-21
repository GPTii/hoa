import { useEffect, useState } from "react";
import { Alert, Button, Card, Collapse, InputNumber, Space, Switch, Table, Tag, Typography, message } from "antd";
import { CalculatorOutlined } from "@ant-design/icons";
import { api } from "../api";
import { useAuth } from "../auth";
import { LEVEL_COLORS, PageHeader } from "../components/common";

const UT: Record<string, string> = { all: "Tất cả", hanh_chinh: "Hành chính", giao_duc: "Giáo dục" };
const MT: Record<string, string> = { ratio: "Tỷ lệ %", boolean: "Có/Không", number: "Số đo" };
const SRC: Record<string, string> = { survey: "Khảo sát", tasks: "Nhiệm vụ", infra: "Hạ tầng", services: "Dịch vụ" };

export default function Framework() {
  const { can } = useAuth();
  const edit = can("criteria.manage");
  const [data, setData] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/framework").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);
  const total = data.reduce((s, p) => s + p.weight, 0);

  const recompute = async () => {
    setBusy(true);
    try { await api.post("/data/recompute", null, { params: { all_periods: true } }); message.success("Đã tính lại DTI cho tất cả các kỳ"); } finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title="Bộ tiêu chí đánh giá mức độ chuyển đổi số" sub="7 trụ cột · tham chiếu Bộ chỉ số DTI của Bộ TT&TT, điều chỉnh cho cấp xã và cơ sở giáo dục"
        extra={edit && <Button type="primary" icon={<CalculatorOutlined />} loading={busy} onClick={recompute}>Áp dụng & tính lại DTI</Button>} />
      <Card size="small" style={{ marginBottom: 16 }}>
        <Typography.Paragraph style={{ marginBottom: 8 }}>
          <b>Công thức:</b> Điểm tiêu chí = min(giá trị / mục tiêu, 1) × 100 (tiêu chí Có/Không: 0 hoặc 100) →
          Điểm trụ cột = trung bình có trọng số các tiêu chí → <b>DTI = Σ(điểm trụ cột × trọng số trụ cột) / Σ trọng số</b>.
          Thiếu dữ liệu khảo sát tính 0 điểm; tiêu chí từ nhiệm vụ chỉ áp dụng khi đơn vị có nhiệm vụ đến hạn trong kỳ.
        </Typography.Paragraph>
        <Space wrap>
          <span>Phân loại:</span>
          {[["< 30", "Khởi đầu"], ["30–50", "Cơ bản"], ["50–70", "Phát triển"], ["70–85", "Nâng cao"], ["≥ 85", "Dẫn đầu"]].map(([r, l]) => <Tag key={l} color={LEVEL_COLORS[l]}>{l}: {r}</Tag>)}
        </Space>
        {Math.abs(total - 100) > 0.01 && <Alert style={{ marginTop: 8 }} type="warning" showIcon message={`Tổng trọng số trụ cột hiện là ${total} (khuyến nghị = 100; hệ thống vẫn chuẩn hóa theo tổng)`} />}
      </Card>
      <Collapse defaultActiveKey={data.map((p) => String(p.id))} items={data.map((p) => ({
        key: String(p.id),
        label: <Space><b>{p.code} · {p.name}</b><span className="muted">{p.description}</span></Space>,
        extra: <Space onClick={(e) => e.stopPropagation()}>Trọng số
          <InputNumber size="small" min={0} max={100} value={p.weight} disabled={!edit}
            onChange={(v) => v != null && api.put(`/framework/pillars/${p.id}`, { weight: v }).then(load)} /></Space>,
        children: <Table size="small" rowKey="id" pagination={false} dataSource={p.criteria} columns={[
          { title: "Mã", dataIndex: "code", width: 70 },
          { title: "Tiêu chí", dataIndex: "name" },
          { title: "Áp dụng", dataIndex: "unit_type", width: 100, render: (v) => UT[v] },
          { title: "Kiểu", dataIndex: "metric_type", width: 90, render: (v) => MT[v] },
          { title: "Nguồn", dataIndex: "source", width: 90, render: (v) => <Tag>{SRC[v]}</Tag> },
          { title: "Mục tiêu", dataIndex: "target", width: 110, render: (v, r: any) => r.metric_type === "boolean" ? "Có" :
            <InputNumber size="small" min={0.01} value={v} disabled={!edit} addonAfter={r.unit_label} style={{ width: 100 }}
              onChange={(nv) => nv && api.put(`/framework/criteria/${r.id}`, { weight: r.weight, target: nv, is_active: r.is_active }).then(load)} /> },
          { title: "Trọng số", dataIndex: "weight", width: 90, render: (v, r: any) =>
            <InputNumber size="small" min={0} max={10} value={v} disabled={!edit} style={{ width: 70 }}
              onChange={(nv) => nv != null && api.put(`/framework/criteria/${r.id}`, { weight: nv, target: r.target, is_active: r.is_active }).then(load)} /> },
          { title: "Sử dụng", dataIndex: "is_active", width: 80, render: (v, r: any) =>
            <Switch size="small" checked={v} disabled={!edit} onChange={(nv) => api.put(`/framework/criteria/${r.id}`, { weight: r.weight, target: r.target, is_active: nv }).then(load)} /> },
        ]} />,
      }))} />
    </>
  );
}
