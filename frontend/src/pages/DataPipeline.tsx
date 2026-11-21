import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Drawer, Row, Select, Space, Table, Tabs, Tag, Typography, Upload, message } from "antd";
import { CloudSyncOutlined, DownloadOutlined, InboxOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { PageHeader, PeriodSelect } from "../components/common";

const LAYER = [
  { k: "source", name: "Dữ liệu nguồn", color: "#1e3a8a", bg: "#e8f0fe", desc: "File khảo sát CSV/Excel, dữ liệu vận hành (nhiệm vụ, hạ tầng, dịch vụ)" },
  { k: "bronze", name: "Bronze", color: "#92400e", bg: "#fbeee4", desc: "Lưu nguyên trạng từng dòng (JSONB) + thông tin lô nhập để truy vết" },
  { k: "silver", name: "Silver", color: "#475569", bg: "#f1f3f6", desc: "Làm sạch, chuẩn hóa: mã đơn vị, kỳ, kiểu dữ liệu, miền giá trị, loại trùng" },
  { k: "gold", name: "Gold", color: "#a16207", bg: "#fdf6dd", desc: "Điểm tiêu chí, trụ cột, DTI, xếp hạng, cảnh báo, đề xuất, phân cụm" },
  { k: "bi", name: "Phân tích", color: "#166534", bg: "#e7f4e9", desc: "Dashboard, báo cáo, hỗ trợ hoạch định" },
];
const STATUS: Record<string, string> = { bronze: "orange", silver: "default", gold: "gold", failed: "red" };
const SRC: Record<string, string> = { upload_csv: "Tải lên CSV", upload_xlsx: "Tải lên Excel", system_sync: "Đồng bộ vận hành", seed: "Khởi tạo" };

export default function DataPipeline() {
  const { can } = useAuth();
  const [data, setData] = useState<any>({ items: [], layers: {}, total: 0 });
  const [page, setPage] = useState(1);
  const [period, setPeriod] = useState<string>();
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>();
  const [view, setView] = useState<any>();
  const [rej, setRej] = useState<any[]>([]);
  const [raw, setRaw] = useState<any[]>([]);
  const [ut, setUt] = useState("hanh_chinh");
  const load = () => api.get("/data/batches", { params: { page } }).then((r) => setData(r.data));
  useEffect(() => { load(); }, [page]);

  const open = (b: any) => {
    setView(b);
    api.get(`/data/batches/${b.id}/rejected`).then((r) => setRej(r.data));
    api.get(`/data/batches/${b.id}/raw`).then((r) => setRaw(r.data));
  };
  const sync = async () => {
    const r = await api.post("/data/sync", null, { params: { period } });
    message.success(r.data.batch.message); setResult(r.data); load();
  };
  const counts: Record<string, any> = { bronze: data.layers.bronze, silver: data.layers.silver, gold: data.layers.gold };

  return (
    <>
      <PageHeader title="Tích hợp & xử lý dữ liệu" sub="Kiến trúc Medallion Bronze – Silver – Gold trên PostgreSQL (schema bronze / silver / gold)"
        extra={<><PeriodSelect value={period} onChange={setPeriod} />
          {can("score.compute") && <Button icon={<CloudSyncOutlined />} onClick={sync}>Đồng bộ dữ liệu vận hành</Button>}</>} />
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
          {LAYER.map((l, i) => (
            <div key={l.k} style={{ background: l.bg, border: `1.5px solid ${l.color}55`, borderRadius: 10, padding: 12, position: "relative" }}>
              <div style={{ color: l.color, fontWeight: 700, fontSize: 16 }}>{i + 1}. {l.name}</div>
              {counts[l.k] != null && <div style={{ fontSize: 22, fontWeight: 700, color: l.color }} className="num">{counts[l.k].toLocaleString("vi-VN")} <span style={{ fontSize: 12, fontWeight: 400 }}>bản ghi</span></div>}
              <div style={{ fontSize: 12, color: "#475569" }}>{l.desc}</div>
            </div>
          ))}
        </div>
      </Card>
      <Row gutter={[16, 16]}>
        {can("data.import") && <Col xs={24} lg={9}>
          <Card size="small" title="Nhập dữ liệu khảo sát">
            <Upload.Dragger accept=".csv,.xlsx,.xls" showUploadList={false} disabled={uploading}
              customRequest={async ({ file }) => {
                setUploading(true);
                const fd = new FormData(); fd.append("file", file as File); if (period) fd.append("period", period);
                try { const r = await api.post("/data/upload", fd); setResult(r.data); message.success(r.data.batch.message ?? "Đã xử lý"); load(); } finally { setUploading(false); }
              }}>
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p>Kéo thả hoặc bấm để chọn tệp CSV / Excel</p>
              <p className="muted" style={{ fontSize: 12 }}>Hỗ trợ dạng bảng rộng (mỗi cột 1 mã tiêu chí) hoặc dạng dài (ma_don_vi, ky, ma_tieu_chi, gia_tri). Tự động chạy Bronze → Silver → Gold.</p>
            </Upload.Dragger>
            <Space style={{ marginTop: 12 }} wrap>
              <Select value={ut} onChange={setUt} style={{ width: 170 }} options={[{ value: "hanh_chinh", label: "Mẫu: Hành chính" }, { value: "giao_duc", label: "Mẫu: Giáo dục" }]} />
              <Button icon={<DownloadOutlined />} onClick={() => download("/data/template", { period, unit_type: ut }, `mau_nhap_${ut}.xlsx`)}>Tải file mẫu</Button>
            </Space>
            {result && (
              <Alert style={{ marginTop: 12 }} type={result.batch.status === "failed" ? "error" : "success"} showIcon
                message={`Lô #${result.batch.id}: ${result.batch.message}`}
                description={(Array.isArray(result.gold) ? result.gold : [result.gold]).filter(Boolean).map((g: any) =>
                  <div key={g.period}>Gold {g.period}: {g.units} đơn vị · DTI TB {g.avg_dti} · {g.alerts} cảnh báo · {g.recommendations} đề xuất</div>)} />
            )}
          </Card>
        </Col>}
        <Col xs={24} lg={can("data.import") ? 15 : 24}>
          <Card size="small" title="Lịch sử lô dữ liệu" extra={<Button size="small" icon={<ReloadOutlined />} onClick={load} />}>
            <Table size="small" rowKey="id" dataSource={data.items} onRow={(b) => ({ onClick: () => open(b), style: { cursor: "pointer" } })}
              pagination={{ current: page, total: data.total, pageSize: 15, onChange: setPage }} columns={[
                { title: "Lô", dataIndex: "id", width: 60 },
                { title: "Nguồn", dataIndex: "source_type", render: (v, b: any) => <div><Tag>{SRC[v] ?? v}</Tag><div style={{ fontSize: 12 }}>{b.file_name}</div></div> },
                { title: "Kỳ", dataIndex: "period_code", width: 80 },
                { title: "Dòng", dataIndex: "total_rows", align: "right", width: 70 },
                { title: "Hợp lệ", dataIndex: "valid_values", align: "right", width: 80 },
                { title: "Lỗi", dataIndex: "rejected_values", align: "right", width: 60, render: (v) => v ? <Tag color="red">{v}</Tag> : 0 },
                { title: "Tầng", dataIndex: "status", width: 80, render: (v) => <Tag color={STATUS[v]}>{v.toUpperCase()}</Tag> },
                { title: "Thời gian", dataIndex: "uploaded_at", width: 130, render: (v) => dayjs(v).format("HH:mm DD/MM/YY"), responsive: ["md"] },
              ]} />
          </Card>
        </Col>
      </Row>
      <Drawer width={860} open={!!view} onClose={() => setView(null)} title={view && `Lô #${view.id} – ${view.file_name}`}>
        {view && <>
          <Typography.Paragraph>{view.message}</Typography.Paragraph>
          <Tabs items={[
            { key: "rej", label: `Bản ghi bị loại ở Silver (${rej.length})`, children: <Table size="small" rowKey={(r) => `${r.row_no}-${r.column_name}`} dataSource={rej} pagination={{ pageSize: 15 }} columns={[
              { title: "Dòng", dataIndex: "row_no", width: 70 }, { title: "Cột", dataIndex: "column_name", width: 120 },
              { title: "Giá trị gốc", dataIndex: "raw_value", width: 140 }, { title: "Lý do", dataIndex: "reason" },
            ]} /> },
            { key: "raw", label: "Dữ liệu thô Bronze (100 dòng đầu)", children: <Table size="small" rowKey="row_no" dataSource={raw} pagination={{ pageSize: 10 }}
              columns={[{ title: "Dòng", dataIndex: "row_no", width: 60 }, { title: "Payload (JSONB)", dataIndex: "payload", render: (v) => <code style={{ fontSize: 11, wordBreak: "break-all" }}>{JSON.stringify(v)}</code> }]} /> },
          ]} />
        </>}
      </Drawer>
    </>
  );
}
