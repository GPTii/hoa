import { Card, Select, Space, Tag, Tooltip, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";

export const LEVEL_COLORS: Record<string, string> = {
  "Khởi đầu": "#dc2626", "Cơ bản": "#ea580c", "Phát triển": "#ca8a04", "Nâng cao": "#16a34a", "Dẫn đầu": "#1d4ed8",
};
export const LEVEL_ORDER = ["Khởi đầu", "Cơ bản", "Phát triển", "Nâng cao", "Dẫn đầu"];
export const PILLAR_NAMES: Record<string, string> = {
  NT: "Nhận thức số", TC: "Thể chế số", HT: "Hạ tầng số", NL: "Nhân lực số", AT: "An toàn TT", HD: "Điều hành số", DV: "Dịch vụ số",
};
export const UNIT_TYPE: Record<string, string> = { hanh_chinh: "Cơ quan hành chính", giao_duc: "Cơ sở giáo dục" };
export const SEVERITY: Record<string, { color: string; text: string }> = {
  cao: { color: "red", text: "Cao" }, trung_binh: { color: "orange", text: "Trung bình" }, thap: { color: "blue", text: "Thấp" },
};
export const ALERT_TYPES: Record<string, string> = {
  LOW_SCORE: "DTI thấp", SCORE_DROP: "Điểm giảm", WEAK_PILLAR: "Trụ cột yếu", OVERDUE_TASK: "Nhiệm vụ trễ hạn",
  MISSING_DATA: "Thiếu dữ liệu", EXPIRING_SERVICE: "Dịch vụ sắp hết hạn",
};
export const TASK_STATUS: Record<string, string> = {
  chua_tiep_nhan: "default", khong_tiep_nhan: "magenta", dang_xu_ly: "processing", cho_kiem_tra: "warning", cho_duyet: "warning", cho_phat_hanh: "processing", da_bao_cao: "gold", hoan_thanh: "success", tra_lai: "error",
};
export const CHART_COLORS = ["#1d4ed8", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#ca8a04", "#dc2626", "#64748b"];

export function scoreColor(s?: number | null) {
  if (s == null) return "#94a3b8";
  if (s >= 85) return LEVEL_COLORS["Dẫn đầu"];
  if (s >= 70) return LEVEL_COLORS["Nâng cao"];
  if (s >= 50) return LEVEL_COLORS["Phát triển"];
  if (s >= 30) return LEVEL_COLORS["Cơ bản"];
  return LEVEL_COLORS["Khởi đầu"];
}

export const LevelTag = ({ level }: { level?: string | null }) =>
  level ? <Tag color={LEVEL_COLORS[level]} style={{ marginInlineEnd: 0 }}>{level}</Tag> : <Tag>Chưa đánh giá</Tag>;

export const Score = ({ v, size = 14 }: { v?: number | null; size?: number }) => (
  <span style={{ color: scoreColor(v), fontWeight: 600, fontSize: size, fontVariantNumeric: "tabular-nums" }}>
    {v == null ? "—" : v.toFixed(1)}
  </span>
);

export const Delta = ({ v }: { v?: number | null }) => {
  if (v == null) return <span style={{ color: "#94a3b8" }}>—</span>;
  const up = v >= 0;
  return (
    <span style={{ color: up ? "#16a34a" : "#dc2626", fontVariantNumeric: "tabular-nums" }}>
      {up ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(v).toFixed(1)}
    </span>
  );
};

export const ScoreBar = ({ v }: { v?: number | null }) => (
  <Tooltip title={v == null ? "Chưa có" : `${v.toFixed(1)} điểm`}>
    <div style={{ background: "#eef2f7", borderRadius: 4, height: 8, width: "100%", minWidth: 60 }}>
      <div style={{ width: `${v ?? 0}%`, background: scoreColor(v), height: 8, borderRadius: 4 }} />
    </div>
  </Tooltip>
);

export type Period = { code: string; name: string; is_current: boolean };

export function usePeriods() {
  const [periods, setPeriods] = useState<Period[]>([]);
  useEffect(() => { api.get("/periods").then((r) => setPeriods(r.data)); }, []);
  const current = periods.find((p) => p.is_current)?.code ?? periods.at(-1)?.code;
  return { periods, current };
}

export function PeriodSelect({ value, onChange }: { value?: string; onChange: (v: string) => void }) {
  const { periods, current } = usePeriods();
  useEffect(() => { if (!value && current) onChange(current); }, [current]);
  return (
    <Select style={{ width: 140 }} value={value} onChange={onChange}
      options={[...periods].reverse().map((p) => ({ value: p.code, label: p.name + (p.is_current ? " (hiện hành)" : "") }))} />
  );
}

export function useRegions() {
  const [regions, setRegions] = useState<{ id: number; name: string; type: string }[]>([]);
  useEffect(() => { api.get("/regions").then((r) => setRegions(r.data)); }, []);
  return regions;
}

export function PageHeader({ title, sub, extra }: { title: string; sub?: ReactNode; extra?: ReactNode }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
      <div>
        <Typography.Title level={3} style={{ margin: 0 }}>{title}</Typography.Title>
        {sub && <Typography.Text type="secondary">{sub}</Typography.Text>}
      </div>
      <Space wrap>{extra}</Space>
    </div>
  );
}

export function Kpi({ title, value, suffix, foot, color }: { title: string; value: ReactNode; suffix?: string; foot?: ReactNode; color?: string }) {
  return (
    <Card size="small" styles={{ body: { padding: 16 } }} style={{ height: "100%" }}>
      <div style={{ color: "#64748b", fontSize: 13 }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color ?? "#0f172a", lineHeight: 1.3, fontVariantNumeric: "tabular-nums" }}>
        {value}{suffix && <span style={{ fontSize: 15, fontWeight: 500, color: "#64748b" }}> {suffix}</span>}
      </div>
      {foot && <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{foot}</div>}
    </Card>
  );
}

export const money = (v: number) => new Intl.NumberFormat("vi-VN").format(Math.round(v)) + " đ";
