import { useEffect, useState } from "react";
import {
  Alert, Button, Card, Checkbox, Col, Descriptions, Drawer, Form, Input, Modal, Row, Segmented, Select, Space, Statistic, Table, Tag, message,
} from "antd";
import { CheckOutlined, NotificationOutlined, RollbackOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader, Score } from "../components/common";
import { ASSESS_STATUS } from "./SelfAssessment";

const fmt = (d?: string) => (d ? dayjs(d).format("HH:mm DD/MM/YYYY") : "");

/** Thẩm định phiếu tự đánh giá: xem số liệu + minh chứng, chấp nhận / điều chỉnh từng tiêu chí, phê duyệt hoặc yêu cầu giải trình */
function ReviewDrawer({ id, onClose, onDone }: { id: number; onClose: () => void; onDone: () => void }) {
  const [a, setA] = useState<any>();
  const [adj, setAdj] = useState<Record<number, { reviewer_value?: string; reviewer_note?: string }>>({});
  const [note, setNote] = useState("");
  useEffect(() => {
    api.get(`/assessments/${id}`).then((r) => {
      setA(r.data);
      setNote(r.data.review_note ?? "");
      setAdj(Object.fromEntries(r.data.items.map((i: any) => [i.criterion_id, { reviewer_value: i.reviewer_value ?? "", reviewer_note: i.reviewer_note ?? "" }])));
    });
  }, [id]);
  const send = async (action: "approve" | "return") => {
    if (action === "return" && !note.trim()) return message.warning("Nhập nội dung yêu cầu giải trình / bổ sung");
    const items = Object.entries(adj).filter(([, v]) => v.reviewer_value || v.reviewer_note)
      .map(([cid, v]) => ({ criterion_id: Number(cid), ...v }));
    const r = await api.post(`/assessments/${id}/review`, { action, note, items });
    message.success(action === "approve" ? `Đã phê duyệt – DTI ${r.data.final_score}` : "Đã trả lại đơn vị");
    onDone();
  };
  const set = (cid: number, k: "reviewer_value" | "reviewer_note", v: string) => setAdj({ ...adj, [cid]: { ...adj[cid], [k]: v } });
  return (
    <Drawer open width={1100} onClose={onClose} title={a ? `Thẩm định phiếu tự đánh giá – ${a.unit_name}` : "..."}
      extra={a?.can_review && <Space>
        <Button danger icon={<RollbackOutlined />} onClick={() => send("return")}>Yêu cầu giải trình</Button>
        <Button type="primary" icon={<CheckOutlined />} onClick={() => Modal.confirm({
          title: "Phê duyệt kết quả thẩm định?", okText: "Phê duyệt",
          content: "Số liệu sau thẩm định được đưa vào kho dữ liệu (Bronze → Silver → Gold) và tính lại chỉ số DTI của kỳ.",
          onOk: () => send("approve") })}>Phê duyệt</Button>
      </Space>}>
      {a && <>
        <Descriptions size="small" bordered column={{ xs: 1, md: 3 }} style={{ marginBottom: 12 }} items={[
          { label: "Đơn vị", children: a.unit_name }, { label: "Địa bàn", children: a.region },
          { label: "Trạng thái", children: <Tag color={ASSESS_STATUS[a.status]}>{a.status_name}</Tag> },
          { label: "Người lập", children: a.prepared_by }, { label: "Lãnh đạo nộp", children: `${a.submitted_by ?? ""} ${fmt(a.submitted_at)}` },
          { label: "Điểm tự chấm (ước tính)", children: a.self_score ?? "—" },
        ]} />
        {a.can_review
          ? <Input.TextArea rows={2} value={note} onChange={(e) => setNote(e.target.value)} style={{ marginBottom: 12 }}
              placeholder="Kết luận thẩm định / nội dung yêu cầu đơn vị giải trình, bổ sung" />
          : a.review_note && <Alert style={{ marginBottom: 12 }} showIcon type="info" message={`Kết luận của ${a.reviewed_by}`} description={a.review_note} />}
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Để trống cột “Giá trị thẩm định” nghĩa là chấp nhận số liệu đơn vị tự khai. Nhập giá trị khác nếu minh chứng không phù hợp." />
        <Table size="small" rowKey="criterion_id" dataSource={a.items} pagination={false} scroll={{ x: 1000 }} columns={[
          { title: "Mã", dataIndex: "code", width: 65 },
          { title: "Tiêu chí", dataIndex: "name", width: 260, render: (v, i: any) => <div>{v}<div className="muted" style={{ fontSize: 12 }}>{i.pillar} · mục tiêu {i.metric_type === "boolean" ? "Có" : i.target}</div></div> },
          { title: "Tự khai", dataIndex: "value_raw", width: 90, render: (v) => <b>{v}</b> },
          { title: "Minh chứng", dataIndex: "evidence", width: 240, render: (v) => v || <Tag color="orange">Không có</Tag> },
          { title: "Giá trị thẩm định", key: "rv", width: 130, render: (_, i: any) => a.can_review
            ? <Input value={adj[i.criterion_id]?.reviewer_value} placeholder="(chấp nhận)" onChange={(e) => set(i.criterion_id, "reviewer_value", e.target.value)} />
            : i.reviewer_value && <Tag color="red">{i.reviewer_value}</Tag> },
          { title: "Ý kiến", key: "rn", width: 200, render: (_, i: any) => a.can_review
            ? <Input value={adj[i.criterion_id]?.reviewer_note} onChange={(e) => set(i.criterion_id, "reviewer_note", e.target.value)} />
            : i.reviewer_note },
        ]} />
      </>}
    </Drawer>
  );
}

export default function Assessments() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [periods, setPeriods] = useState<any[]>([]);
  const [period, setPeriod] = useState<string>();
  const [status, setStatus] = useState<string>(can("assess.review") ? "da_nop" : "all");
  const [d, setD] = useState<any>();
  const [open, setOpen] = useState<number | null>(sp.get("id") ? Number(sp.get("id")) : null);
  const [pubForm] = Form.useForm();
  useEffect(() => {
    api.get("/periods").then((r) => { setPeriods(r.data); setPeriod(r.data.find((p: any) => p.is_current)?.code); });
  }, []);
  const load = () => period && api.get("/assessments", { params: { period } }).then((r) => setD(r.data));
  useEffect(() => { load(); }, [period]);
  const publish = () => Modal.confirm({
    title: `Công bố kết quả đánh giá ${d.period.name}`, okText: "Công bố", width: 520,
    content: <Form form={pubForm} layout="vertical" initialValues={{ lock: true }}>
      <Alert type="warning" showIcon style={{ marginBottom: 12 }}
        message="Kết quả sau công bố là chính thức: thông báo tới toàn bộ người dùng; số liệu kỳ được khóa (trừ kỳ hiện hành)." />
      <Form.Item name="decision" label="Số quyết định công bố" rules={[{ required: true }]}><Input placeholder="VD: 1520/QĐ-UBND" /></Form.Item>
      <Form.Item name="lock" valuePropName="checked"><Checkbox>Khóa số liệu kỳ sau khi công bố</Checkbox></Form.Item>
    </Form>,
    onOk: async () => {
      const v = await pubForm.validateFields();
      await api.post(`/assessments/publish/${d.period.code}`, v);
      message.success("Đã công bố kết quả");
      api.get("/periods").then((r) => setPeriods(r.data));
      load();
    },
  });
  const items = (d?.items ?? []).filter((a: any) => status === "all" || a.status === status);
  const c = d?.counts ?? {};
  return (
    <>
      <PageHeader title={can("assess.review") ? "Thẩm định kết quả tự đánh giá" : "Kết quả đánh giá chuyển đổi số"}
        sub="Đơn vị tự đánh giá → cơ quan thẩm định (Sở KH&CN với cơ quan hành chính, Sở GD&ĐT với cơ sở giáo dục) → UBND tỉnh công bố"
        extra={<Select style={{ width: 230 }} value={period} onChange={setPeriod} options={periods.map((p) => ({
          value: p.code, label: <Space>{p.name}{p.published_at ? <Tag color="green">Đã công bố</Tag> : <Tag>Tạm tính</Tag>}</Space> }))} />} />
      {d && <>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          {[["Đang lập", c.nhap, "#2563eb"], ["Chờ thẩm định", c.da_nop, "#ea580c"], ["Trả lại giải trình", c.tra_lai, "#dc2626"],
            ["Đã thẩm định", c.da_tham_dinh, "#16a34a"]].map(([t, v, col]) => (
            <Col xs={12} md={6} key={t as string}><Card size="small"><Statistic title={t} value={v as number ?? 0} valueStyle={{ color: col as string }} /></Card></Col>))}
        </Row>
        {can("assess.publish") && (d.period.published_at
          ? <Alert type="success" showIcon style={{ marginBottom: 16 }} icon={<NotificationOutlined />}
              message={`Đã công bố theo Quyết định ${d.period.publish_decision} ngày ${dayjs(d.period.published_at).format("DD/MM/YYYY")} (${d.period.published_by})`}
              description={d.period.is_locked ? "Số liệu kỳ đã khóa." : undefined} />
          : <Alert type={c.da_nop ? "warning" : "info"} showIcon style={{ marginBottom: 16 }}
              message={c.da_nop ? `Còn ${c.da_nop} phiếu chờ thẩm định – thẩm định xong mới công bố được` : "Các phiếu đã nộp đều đã thẩm định – có thể công bố kết quả chính thức của kỳ"}
              action={<Button type="primary" icon={<NotificationOutlined />} disabled={!!c.da_nop} onClick={publish}>Công bố kết quả</Button>} />)}
        <Card size="small" extra={<Segmented value={status} onChange={(v) => setStatus(v as string)} options={[
          { value: "da_nop", label: `Chờ thẩm định (${c.da_nop ?? 0})` }, { value: "tra_lai", label: "Trả lại" },
          { value: "da_tham_dinh", label: "Đã thẩm định" }, { value: "nhap", label: "Đang lập" }, { value: "all", label: "Tất cả" }]} />}>
          <Table size="small" rowKey="id" dataSource={items} scroll={{ x: 1000 }} pagination={{ pageSize: 15 }} columns={[
            { title: "Đơn vị", dataIndex: "unit_name", width: 260, render: (v, a: any) => <a onClick={() => setOpen(a.id)}>{v}</a> },
            { title: "Địa bàn", dataIndex: "region", width: 160 },
            { title: "Trạng thái", dataIndex: "status_name", width: 190, render: (v, a: any) => <Tag color={ASSESS_STATUS[a.status]}>{v}</Tag> },
            { title: "Đã khai", key: "f", width: 90, render: (_, a: any) => `${a.filled}/${a.total}` },
            { title: "Nộp lúc", dataIndex: "submitted_at", width: 140, render: fmt },
            { title: "Tự chấm", dataIndex: "self_score", width: 90 },
            { title: "Sau thẩm định", dataIndex: "final_score", width: 120, render: (v) => v != null ? <Score v={v} /> : "—" },
            { title: "Điều chỉnh", dataIndex: "adjusted", width: 90, render: (v) => v ? <Tag color="red">{v} tiêu chí</Tag> : "—" },
            { title: "", key: "x", width: 110, render: (_, a: any) => <Button size="small" type={a.status === "da_nop" && can("assess.review") ? "primary" : "default"}
              onClick={() => setOpen(a.id)}>{a.status === "da_nop" && can("assess.review") ? "Thẩm định" : "Xem"}</Button> },
          ]} />
        </Card>
      </>}
      {open && <ReviewDrawer id={open} onClose={() => { setOpen(null); setSp({}); }} onDone={() => { setOpen(null); setSp({}); load(); }} />}
    </>
  );
}
