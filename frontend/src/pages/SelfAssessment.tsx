import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Input, Modal, Progress, Row, Select, Space, Statistic, Steps, Table, Tag, message } from "antd";
import { SaveOutlined, SendOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/common";

export const ASSESS_STATUS: Record<string, string> = { nhap: "processing", da_nop: "warning", tra_lai: "error", da_tham_dinh: "success" };
const STEP: Record<string, number> = { nhap: 0, tra_lai: 0, da_nop: 2, da_tham_dinh: 3 };

/** Phiếu tự đánh giá mức độ chuyển đổi số của đơn vị trong kỳ:
 *  chuyên viên/giáo viên khai số liệu + minh chứng → lãnh đạo đơn vị duyệt, nộp → cơ quan thẩm định → UBND tỉnh công bố. */
export default function SelfAssessment() {
  const { can } = useAuth();
  const [a, setA] = useState<any>();
  const [items, setItems] = useState<Record<number, { value_raw?: string; evidence?: string }>>({});
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<string>("all");
  const load = () => api.get("/assessments/mine").then((r) => {
    setA(r.data);
    setItems(Object.fromEntries(r.data.items.map((i: any) => [i.criterion_id, { value_raw: i.value_raw ?? "", evidence: i.evidence ?? "" }])));
  });
  useEffect(() => { load(); }, []);
  if (!a) return null;
  const set = (cid: number, k: "value_raw" | "evidence", v: string) => setItems({ ...items, [cid]: { ...items[cid], [k]: v } });
  const save = async (quiet = false) => {
    setSaving(true);
    try {
      const r = await api.put(`/assessments/${a.id}/items`, Object.entries(items).map(([cid, v]) => ({ criterion_id: Number(cid), ...v })));
      if (r.data.errors.length) Modal.warning({ title: "Một số giá trị không hợp lệ", content: <ul>{r.data.errors.map((e: string) => <li key={e}>{e}</li>)}</ul> });
      else if (!quiet) message.success("Đã lưu phiếu");
      await load();
      return !r.data.errors.length;
    } finally { setSaving(false); }
  };
  const submit = () => {
    let note = "";
    Modal.confirm({
      title: "Duyệt và nộp phiếu tự đánh giá?", okText: "Nộp cơ quan thẩm định",
      content: <><p>Sau khi nộp, phiếu bị khóa chỉnh sửa cho tới khi cơ quan thẩm định trả lại.</p>
        <Input.TextArea rows={2} placeholder="Ghi chú gửi cơ quan thẩm định (không bắt buộc)" onChange={(e) => { note = e.target.value; }} /></>,
      onOk: async () => {
        if (!(await save(true))) return;
        await api.post(`/assessments/${a.id}/submit`, { note });
        message.success("Đã nộp phiếu tự đánh giá");
        load();
      },
    });
  };
  const filled = a.items.filter((i: any) => (items[i.criterion_id]?.value_raw ?? "").trim()).length;
  const withEv = a.items.filter((i: any) => (items[i.criterion_id]?.evidence ?? "").trim()).length;
  const rows = a.items.filter((i: any) => filter === "all" || (filter === "empty" ? !(items[i.criterion_id]?.value_raw ?? "").trim()
    : filter === "adjusted" ? i.reviewer_value || i.reviewer_note : !(items[i.criterion_id]?.evidence ?? "").trim()));
  const ro = !a.can_edit;

  return (
    <>
      <PageHeader title="Tự đánh giá mức độ chuyển đổi số" sub={`${a.unit_name} · ${a.period.name}`}
        extra={<Space>
          {!ro && <Button icon={<SaveOutlined />} loading={saving} onClick={() => save()}>Lưu nháp</Button>}
          {a.can_submit && <Button type="primary" icon={<SendOutlined />} onClick={submit}>Duyệt & nộp</Button>}
        </Space>} />
      <Card size="small" style={{ marginBottom: 16 }}>
        <Steps size="small" current={STEP[a.status]} status={a.status === "tra_lai" ? "error" : undefined} items={[
          { title: "Đơn vị lập phiếu", description: a.prepared_by },
          { title: "Lãnh đạo duyệt, nộp", description: a.submitted_by },
          { title: "Cơ quan thẩm định", description: a.reviewed_by ?? (a.unit_type === "giao_duc" ? "Sở GD&ĐT" : "Sở KH&CN") },
          { title: "UBND tỉnh công bố", description: a.period.published_at ? dayjs(a.period.published_at).format("DD/MM/YYYY") : "Chờ công bố" },
        ]} />
      </Card>
      {a.status === "tra_lai" && <Alert type="error" showIcon style={{ marginBottom: 16 }} message="Cơ quan thẩm định yêu cầu giải trình / bổ sung"
        description={<>{a.review_note}<div className="muted">{a.reviewed_by} · {dayjs(a.reviewed_at).format("HH:mm DD/MM/YYYY")}</div></>} />}
      {a.status === "da_tham_dinh" && <Alert type="success" showIcon style={{ marginBottom: 16 }}
        message={`Đã thẩm định – DTI ${a.final_score ?? "—"} ${a.period.published_at ? "(chính thức)" : "(tạm tính, chờ UBND tỉnh công bố)"}`}
        description={a.review_note} />}
      {a.status === "da_nop" && <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="Phiếu đã nộp, đang chờ cơ quan thẩm định" />}
      {a.period.is_locked && <Alert type="info" showIcon style={{ marginBottom: 16 }} message="Kỳ đã khóa số liệu" />}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Tiêu chí đã khai" value={filled} suffix={`/ ${a.total}`} />
          <Progress percent={Math.round(filled * 100 / Math.max(a.total, 1))} size="small" showInfo={false} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Có minh chứng" value={withEv} suffix={`/ ${a.total}`} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Điểm tự chấm (ước tính)" value={a.self_score ?? "—"} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Tiêu chí bị điều chỉnh" value={a.adjusted} valueStyle={{ color: a.adjusted ? "#dc2626" : undefined }} /></Card></Col>
      </Row>
      <Card size="small" title="Các tiêu chí đơn vị tự khai"
        extra={<Select value={filter} onChange={setFilter} style={{ width: 200 }} options={[
          { value: "all", label: "Tất cả tiêu chí" }, { value: "empty", label: "Chưa khai giá trị" },
          { value: "noev", label: "Chưa có minh chứng" }, { value: "adjusted", label: "Có ý kiến thẩm định" }]} />}>
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Giá trị đã gợi ý sẵn theo số liệu kỳ trước. Các tiêu chí lấy tự động từ hệ thống (tỷ lệ hoàn thành nhiệm vụ đúng hạn, hạ tầng, dịch vụ số đang dùng) không cần khai."
          description={can("assess.submit") ? "Bạn là lãnh đạo đơn vị: kiểm tra phiếu do chuyên viên lập, chỉnh nếu cần rồi bấm “Duyệt & nộp”." : "Lập xong, báo lãnh đạo đơn vị duyệt và nộp phiếu."} />
        <Table size="small" rowKey="criterion_id" dataSource={rows} pagination={false} scroll={{ x: 1100 }} columns={[
          { title: "Mã", dataIndex: "code", width: 70 },
          { title: "Tiêu chí", dataIndex: "name", width: 300, render: (v, i: any) => <div>{v}<div className="muted" style={{ fontSize: 12 }}>{i.pillar} · mục tiêu {i.metric_type === "boolean" ? "Có" : `${i.target}${i.unit_label ? " " + i.unit_label : ""}`}</div></div> },
          { title: "Giá trị tự khai", key: "v", width: 160, render: (_, i: any) => i.metric_type === "boolean"
            ? <Select disabled={ro} style={{ width: "100%" }} value={items[i.criterion_id]?.value_raw || undefined} placeholder="Chọn"
                onChange={(v) => set(i.criterion_id, "value_raw", v)} options={[{ value: "Có", label: "Có" }, { value: "Không", label: "Không" }]} />
            : <Input disabled={ro} value={items[i.criterion_id]?.value_raw} suffix={i.metric_type === "ratio" ? "%" : undefined}
                onChange={(e) => set(i.criterion_id, "value_raw", e.target.value)} /> },
          { title: "Minh chứng (số văn bản, đường dẫn, mô tả)", key: "e", width: 320, render: (_, i: any) =>
            <Input.TextArea disabled={ro} autoSize={{ minRows: 1, maxRows: 3 }} value={items[i.criterion_id]?.evidence}
              onChange={(e) => set(i.criterion_id, "evidence", e.target.value)} /> },
          { title: "Ý kiến thẩm định", key: "r", width: 220, render: (_, i: any) => (i.reviewer_value || i.reviewer_note) && <div style={{ fontSize: 12 }}>
            {i.reviewer_value && <Tag color="red">Điều chỉnh: {i.reviewer_value}</Tag>}{i.reviewer_note}</div> },
        ]} />
      </Card>
    </>
  );
}
