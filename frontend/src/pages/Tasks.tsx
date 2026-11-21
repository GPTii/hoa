import { useEffect, useState } from "react";
import {
  Alert, Badge, Button, Card, Col, DatePicker, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Progress, Row,
  Segmented, Select, Space, Steps, Table, Tabs, Tag, Timeline, Tree, Typography,
} from "antd";
import { ApartmentOutlined, BankOutlined, BellOutlined, BranchesOutlined, HomeOutlined, PaperClipOutlined, PlusOutlined, ReadOutlined, SendOutlined, UploadOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { Upload, message } from "antd";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader, PILLAR_NAMES, TASK_STATUS } from "../components/common";

const ACTION_NAMES: Record<string, string> = {
  giao_nhiem_vu: "Giao nhiệm vụ", tiep_nhan: "Tiếp nhận", khong_tiep_nhan: "Không tiếp nhận", cap_nhat: "Cập nhật tiến độ",
  bao_cao: "Ký duyệt văn bản", xac_nhan: "Xác nhận hoàn thành", tra_lai: "Trả lại – yêu cầu bổ sung", giao_tiep: "Giao tiếp cho cấp dưới", don_doc: "Đôn đốc",
  phan_cong: "Phân công xử lý", trinh: "Trình dự thảo", tra_ve_xu_ly: "Trả về xử lý lại",
  kiem_tra: "Kiểm tra dự thảo, trình ký", ky_duyet: "Ký duyệt văn bản", phat_hanh: "Cấp số & phát hành văn bản đi",
};
const fmt = (d?: string) => (d ? dayjs(d).format("DD/MM/YYYY") : "");
const unitIcon = (cat?: string) => cat === "ubnd_xa" ? <HomeOutlined /> : cat && ["mam_non", "tieu_hoc", "thcs", "thpt"].includes(cat) ? <ReadOutlined /> : <BankOutlined />;

export function ActionModal({ a, action, onDone, onClose }: { a: any; action: string; onDone: () => void; onClose: () => void }) {
  const [form] = Form.useForm();
  const submit = async () => {
    const v = await form.validateFields();
    await api.post(`/tasks/assignments/${a.id}/action`, { action, ...v });
    onDone();
  };
  return (
    <Modal open title={`${ACTION_NAMES[action]} – ${a.unit_name}`} onOk={submit} onCancel={onClose} okText="Xác nhận">
      {action === "ky_duyet" && a.child && <Alert style={{ marginBottom: 12 }} type="info" showIcon
        message={`Tổng hợp từ ${a.child.done}/${a.child.total} đơn vị cấp dưới đã hoàn thành`} />}
      <Form form={form} layout="vertical">
        {action === "tiep_nhan" && <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Văn bản được vào sổ văn bản đến và chuyển lãnh đạo cho ý kiến, phân công." />}
        {action === "ky_duyet" && <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Sau khi ký, văn thư cấp số, ngày ban hành, đăng ký sổ văn bản đi và phát hành đến cơ quan giao (NĐ 30/2020)."
          description={a.reviewed_by ? `Dự thảo đã được ${a.reviewed_by} kiểm tra.` : undefined} />}
        {action === "phat_hanh" && <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message={`Văn bản đã được ${a.signed_by ?? "lãnh đạo"} ký. Hệ thống cấp số văn bản đi tiếp theo trong sổ của đơn vị và gửi đến cơ quan giao.`} />}
        {action === "kiem_tra" && <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Kiểm tra nội dung, số liệu và thể thức dự thảo; đạt thì trình lãnh đạo ký, chưa đạt thì trả về công chức." />}
        {action === "phan_cong" && <>
          <Form.Item name="handler_dept" label="Phòng / bộ phận chủ trì" initialValue={a.handler_dept ?? (a.unit_type === "giao_duc" ? "Tổ chuyên môn" : "Phòng Văn hóa – Xã hội")}>
            <Select options={(a.unit_type === "giao_duc" ? ["Tổ chuyên môn", "Tổ Tin học", "Văn phòng nhà trường"] : ["Phòng Văn hóa – Xã hội", "Phòng Kinh tế", "Văn phòng HĐND và UBND", "Trung tâm phục vụ hành chính công"]).map((v) => ({ value: v, label: v }))} />
          </Form.Item>
          <Form.Item name="handler_name" label="Công chức / giáo viên được giao" initialValue={a.handler_name}><Input /></Form.Item>
          <Form.Item name="opinion" label="Ý kiến chỉ đạo (bút phê)" initialValue={a.leader_opinion}><Input.TextArea rows={2} placeholder="VD: Giao Phòng VH-XH chủ trì, báo cáo trước ngày ..." /></Form.Item>
        </>}
        {action === "cap_nhat" && <Form.Item name="progress" label="Tiến độ (%)" initialValue={a.progress}><InputNumber min={0} max={100} /></Form.Item>}
        <Form.Item name="note" label={action === "khong_tiep_nhan" ? "Lý do không tiếp nhận" : action === "tra_lai" ? "Nội dung yêu cầu bổ sung"
          : action === "trinh" ? "Nội dung dự thảo báo cáo" : action === "tra_ve_xu_ly" ? "Ý kiến khi trả về (nội dung cần sửa)"
          : action === "kiem_tra" ? "Ý kiến kiểm tra" : action === "ky_duyet" ? "Trích yếu / ghi chú văn bản báo cáo" : "Ghi chú"}
          initialValue={action === "ky_duyet" ? a.report_note : undefined}
          rules={[{ required: ["khong_tiep_nhan", "tra_lai", "tra_ve_xu_ly"].includes(action) }]}><Input.TextArea rows={3} /></Form.Item>
      </Form>
    </Modal>
  );
}

/** UBND xã giao tiếp nhiệm vụ của tỉnh xuống các trường trên địa bàn */
function CascadeModal({ a, task, onDone, onClose }: { a: any; task: any; onDone: (childId: number) => void; onClose: () => void }) {
  const [form] = Form.useForm();
  const [subs, setSubs] = useState<any[]>([]);
  useEffect(() => {
    api.get(`/tasks/assignments/${a.id}/subordinates`).then((r) => {
      setSubs(r.data);
      form.setFieldsValue({ lead_unit_ids: r.data.map((s: any) => s.id) });
    });
  }, []);
  const parentDl = dayjs(task.deadline);
  const submit = async () => {
    const v = await form.validateFields();
    const r = await api.post(`/tasks/assignments/${a.id}/cascade`, { ...v, deadline: v.deadline.format("YYYY-MM-DD") });
    onDone(r.data.id);
  };
  return (
    <Modal open width={640} title={<Space><BranchesOutlined />Giao tiếp nhiệm vụ cho cấp dưới – {a.unit_name}</Space>}
      onOk={submit} onCancel={onClose} okText="Phát hành & giao tiếp" okButtonProps={{ icon: <SendOutlined /> }}>
      <Alert type="info" showIcon style={{ marginBottom: 12 }}
        message={`Nhiệm vụ cấp trên: ${task.code} (${task.assigner_name}) – hạn ${fmt(task.deadline)}`}
        description="Hạn của cấp dưới phải trước hạn cấp trên để còn thời gian tổng hợp. Xã chỉ gửi báo cáo lên tỉnh khi các trường đã được xác nhận xong." />
      <Form form={form} layout="vertical" initialValues={{
        title: task.title, deadline: parentDl.subtract(5, "day").isBefore(dayjs()) ? parentDl : parentDl.subtract(5, "day"),
      }}>
        <Form.Item name="title" label="Trích yếu"><Input /></Form.Item>
        <Row gutter={12}>
          <Col span={12}><Form.Item name="doc_number" label="Số/ký hiệu văn bản giao tiếp"><Input placeholder="VD: 215/UBND-VHXH" /></Form.Item></Col>
          <Col span={12}><Form.Item name="deadline" label="Hạn báo cáo của cấp dưới" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" disabledDate={(d) => d.isBefore(dayjs(), "day") || d.isAfter(parentDl, "day")} /></Form.Item></Col>
        </Row>
        <Form.Item name="content" label="Nội dung chỉ đạo bổ sung"><Input.TextArea rows={2} /></Form.Item>
        <Form.Item name="lead_unit_ids" label={`Đơn vị cấp dưới nhận (${subs.length} trường do xã/phường quản lý)`} rules={[{ required: true }]}>
          <Select mode="multiple" options={subs.map((s) => ({ value: s.id, label: s.name }))} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

/** Sơ đồ luồng liên thông: Cơ quan giao → đơn vị nhận → cấp dưới */
function FlowTree({ taskId, onOpen }: { taskId: number; onOpen: (id: number) => void }) {
  const [tree, setTree] = useState<any>();
  useEffect(() => { api.get(`/tasks/${taskId}/tree`).then((r) => setTree(r.data)); }, [taskId]);
  if (!tree) return <Empty />;
  const unitNode = (u: any, key: string): any => ({
    key, icon: unitIcon(u.unit_category),
    title: <Space size={6} wrap>
      <span style={{ fontWeight: u.children ? 600 : 400 }}>{u.unit_name}</span>
      <Badge status={TASK_STATUS[u.status] as any} text={<span style={{ fontSize: 12 }}>{u.status_name}</span>} />
      <span className="muted" style={{ fontSize: 12 }}>{u.progress}%</span>
      {u.overdue && <Tag color="red">Quá hạn</Tag>}
      {u.children && <Tag color="blue" style={{ cursor: "pointer" }} onClick={() => onOpen(u.children.task_id)}>
        giao tiếp {u.children.code} · {u.children.units.filter((c: any) => ["hoan_thanh", "khong_tiep_nhan"].includes(c.status)).length}/{u.children.units.length} xong</Tag>}
    </Space>,
    children: u.children?.units.map((c: any) => unitNode(c, `${key}-${c.id}`)),
  });
  const done = tree.units.filter((u: any) => u.status === "hoan_thanh").length;
  return (
    <>
      <Alert style={{ marginBottom: 12 }} type="success" showIcon icon={<ApartmentOutlined />}
        message={<>Luồng liên thông từ nhiệm vụ gốc <b>{tree.code}</b> – {tree.assigner}</>}
        description={`${done}/${tree.units.length} đơn vị cấp 1 hoàn thành · hạn ${fmt(tree.deadline)}. Bấm thẻ "giao tiếp" để mở nhiệm vụ cấp dưới.`} />
      <Tree showIcon defaultExpandAll selectable={false} treeData={[{
        key: "root", icon: <BankOutlined />, title: <b>{tree.assigner} – {tree.title}</b>,
        children: tree.units.map((u: any) => unitNode(u, `u-${u.id}`)),
      }]} style={{ background: "transparent" }} />
    </>
  );
}

export function TaskDetail({ id: initialId, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { user, can } = useAuth();
  const [id, setId] = useState(initialId);
  const [t, setT] = useState<any>();
  const [act, setAct] = useState<{ a: any; action: string } | null>(null);
  const [cascadeFor, setCascadeFor] = useState<any>(null);
  const [tab, setTab] = useState("units");
  const [files, setFiles] = useState<any[]>([]);
  const load = () => {
    api.get(`/tasks/${id}`).then((r) => setT(r.data));
    api.get(`/tasks/${id}/attachments`).then((r) => setFiles(r.data));
  };
  useEffect(() => { setT(undefined); load(); }, [id]);
  const remind = (a: any) => Modal.confirm({
    title: `Đôn đốc ${a.unit_name}?`, content: "Gửi thông báo nhắc việc tới văn thư, lãnh đạo và người xử lý của đơn vị.",
    okText: "Gửi đôn đốc", onOk: () => api.post(`/tasks/assignments/${a.id}/remind`, { note: a.overdue ? "Nhiệm vụ đã quá hạn, đề nghị khẩn trương báo cáo." : "Đề nghị hoàn thành đúng hạn." })
      .then(() => { message.success("Đã gửi đôn đốc"); load(); }),
  });
  const myAssignment = t?.assignments.find((a: any) => user?.unit?.id === a.unit_id);
  const canUploadDoc = t && (user?.role.code === "admin" || (can("task.assign") && user?.unit?.id === t.assigner_unit_id));
  const canUploadReport = myAssignment && (can("task.process") || can("task.sign"));
  const doUpload = (assignmentId?: number) => async ({ file }: any) => {
    const fd = new FormData(); fd.append("file", file); if (assignmentId) fd.append("assignment_id", String(assignmentId));
    await api.post(`/tasks/${id}/attachments`, fd); message.success("Đã đính kèm"); load();
  };
  const dl = async (x: any) => {
    const r = await api.get(`/tasks/attachments/${x.id}/download`, { responseType: "blob" });
    const el = document.createElement("a"); el.href = URL.createObjectURL(r.data); el.download = x.file_name; el.click();
  };
  const isAdmin = user?.role.code === "admin";
  const own = (a: any) => isAdmin || user?.unit?.id === a.unit_id;
  const may = (p: string) => isAdmin || can(p);
  const assigner = t && (isAdmin || (can("task.confirm") && (user?.unit?.id === t.assigner_unit_id || user?.role.data_scope === "all")));
  const canCascade = (a: any) => (isAdmin || (can("task.assign") && user?.unit?.id === a.unit_id)) && a.unit_category === "ubnd_xa"
    && ["dang_xu_ly", "tra_lai"].includes(a.status);

  const buttons = (a: any) => {
    const b: [string, string, boolean?][] = [];
    const working = ["dang_xu_ly", "tra_lai"].includes(a.status);
    if (own(a)) {
      // mỗi nút chỉ hiện với chức danh có quyền tương ứng (văn thư / lãnh đạo / trưởng phòng / công chức)
      if (a.status === "chua_tiep_nhan" && may("task.receive")) b.push(["tiep_nhan", "Tiếp nhận", true], ["khong_tiep_nhan", "Không tiếp nhận"]);
      if (working && may("task.dispatch")) b.push(["phan_cong", "Phân công"]);
      if (working && may("task.process")) b.push(["cap_nhat", "Cập nhật"], ["trinh", "Trình dự thảo", !may("task.sign")]);
      if (a.status === "cho_kiem_tra" && may("task.review")) b.push(["kiem_tra", "Kiểm tra, trình ký", true], ["tra_ve_xu_ly", "Trả về"]);
      if ((working || a.status === "cho_duyet") && may("task.sign")) b.push(["ky_duyet", "Ký duyệt", true]);
      if (["cho_duyet", "cho_kiem_tra"].includes(a.status) && may("task.sign")) b.push(["tra_ve_xu_ly", "Trả về xử lý"]);
      if (a.status === "cho_phat_hanh" && may("task.issue")) b.push(["phat_hanh", "Cấp số & phát hành", true]);
    }
    if (assigner && a.status === "da_bao_cao") b.push(["xac_nhan", "Xác nhận hoàn thành", true], ["tra_lai", "Trả lại"]);
    const canRemind = (isAdmin || (may("task.assign") || may("task.confirm")) && (user?.unit?.id === t.assigner_unit_id || user?.role.data_scope === "all"))
      && !["hoan_thanh", "khong_tiep_nhan", "da_bao_cao"].includes(a.status) && !own(a);
    if (own(a) && !b.length && !canCascade(a) && !["hoan_thanh", "khong_tiep_nhan", "da_bao_cao"].includes(a.status)) {
      const hint: Record<string, string> = { chua_tiep_nhan: "Chờ văn thư tiếp nhận", cho_kiem_tra: "Chờ trưởng phòng kiểm tra dự thảo", cho_duyet: "Chờ lãnh đạo ký duyệt",
        cho_phat_hanh: "Đã ký – chờ văn thư cấp số, phát hành", dang_xu_ly: "Chờ lãnh đạo phân công / công chức xử lý", tra_lai: "Chờ công chức xử lý lại" };
      return <span className="muted" style={{ fontSize: 12 }}>{hint[a.status]}</span>;
    }
    return <Space wrap>
      {canCascade(a) && <Button size="small" icon={<BranchesOutlined />} type={a.child ? "default" : "primary"} ghost={!a.child}
        onClick={() => setCascadeFor(a)}>{a.child ? "Bổ sung trường" : "Giao tiếp cho trường"}</Button>}
      {b.map(([k, n, p]) => <Button key={k} size="small" type={p ? "primary" : "default"} onClick={() => setAct({ a, action: k })}>{n}</Button>)}
      {canRemind && <Button size="small" danger={a.overdue} icon={<BellOutlined />} onClick={() => remind(a)}>Đôn đốc</Button>}
    </Space>;
  };

  return (
    <Drawer width={1040} open onClose={onClose} title={t ? <Space>{t.is_cascaded && <Tag color="purple">Giao tiếp</Tag>}{t.code} · {t.title}</Space> : "..."}>
      {t && <>
        {t.parent && <Alert style={{ marginBottom: 12 }} type="warning" showIcon icon={<BranchesOutlined />}
          message={<>Nhiệm vụ giao tiếp từ <a onClick={() => setId(t.parent.task_id)}>{t.parent.code}</a> của {t.parent.assigner_name} (hạn cấp trên {fmt(t.parent.deadline)})</>}
          description={`Trạng thái của ${t.assigner_name} với cấp trên: ${t.parent.status_name}`} />}
        <Descriptions size="small" bordered column={{ xs: 1, md: 3 }} items={[
          { label: "Cơ quan giao", children: t.assigner_name }, { label: "Văn bản", children: `${t.doc_number ?? ""} ${t.doc_date ? "ngày " + fmt(t.doc_date) : ""}` },
          { label: "Hạn xử lý", children: <b style={{ color: dayjs(t.deadline).isBefore(dayjs(), "day") ? "#dc2626" : undefined }}>{fmt(t.deadline)}</b> },
          { label: "Độ khẩn", children: t.priority === "khan" ? <Tag color="red">Khẩn</Tag> : "Thường" },
          { label: "Trụ cột liên quan", children: PILLAR_NAMES[t.pillar_code] ?? "—" },
          { label: "Kết quả", children: `${t.done_units}/${t.total_units} đơn vị hoàn thành${t.cascaded_units ? ` · ${t.cascaded_units} đã giao tiếp` : ""}` },
          { label: "Nội dung", children: t.content, span: 3 },
        ]} />
        <Tabs activeKey={tab} onChange={setTab} style={{ marginTop: 8 }} items={[
          { key: "units", label: "Đơn vị xử lý", children: <>
            <Alert style={{ marginBottom: 12 }} type="info" showIcon
              message="Đã nhận văn bản ≠ hoàn thành; đã gửi báo cáo ≠ hoàn thành. Đơn vị trung gian (xã) chỉ báo cáo lên khi các trường cấp dưới đã được xác nhận." />
            <Table size="small" rowKey="id" dataSource={t.assignments} pagination={{ pageSize: 10 }} scroll={{ x: 1000 }} columns={[
              { title: "Đơn vị", dataIndex: "unit_name", width: 220, render: (v, a: any) => <div>{unitIcon(a.unit_category)} {v} {a.role === "phoi_hop" && <Tag>Phối hợp</Tag>}<div className="muted" style={{ fontSize: 12 }}>{a.incoming_no && <Tag style={{ fontSize: 11 }}>Số đến {a.incoming_no}</Tag>}{a.handler_dept} {a.handler_name && "· " + a.handler_name}</div></div> },
              { title: "Trạng thái", dataIndex: "status_name", width: 180, render: (v, a: any) => <Space direction="vertical" size={0}><Badge status={TASK_STATUS[a.status] as any} text={v} />{a.overdue && <Tag color="red">Quá hạn</Tag>}{a.late_done && <Tag color="orange">Hoàn thành trễ</Tag>}</Space> },
              { title: "Tiến độ", dataIndex: "progress", width: 110, render: (v) => <Progress percent={v} size="small" /> },
              { title: "Cấp dưới (trường)", key: "child", width: 150, render: (_, a: any) => a.child
                ? <a onClick={() => setId(a.child.task_ids[0])}><Progress size="small" percent={Math.round(a.child.done * 100 / a.child.total)} format={() => `${a.child.done}/${a.child.total}`} />
                  {a.child.overdue > 0 && <Tag color="red">{a.child.overdue} quá hạn</Tag>}</a>
                : <span className="muted">—</span> },
              { title: "Văn bản trả lời", dataIndex: "report_doc_number", width: 170, render: (v, a: any) => <div style={{ fontSize: 12 }}>
                {a.leader_opinion && <div title="Ý kiến chỉ đạo"><Tag color="purple" style={{ fontSize: 11 }}>Bút phê</Tag>{a.leader_opinion}</div>}
                {a.reviewed_by && <div className="muted">Kiểm tra: {a.reviewed_by}</div>}
                {a.signed_by && <div className="muted">Ký: {a.signed_by}</div>}
                {v && <div><b>{v}</b> <span className="muted">· {fmt(a.issued_at ?? a.reported_at)}</span></div>}
              </div> },
              { title: "Thao tác", key: "act", width: 280, render: (_, a: any) => buttons(a) },
            ]} />
          </> },
          { key: "flow", label: <Space><ApartmentOutlined />Sơ đồ luồng Tỉnh → Xã → Trường</Space>, children: <FlowTree key={id} taskId={id} onOpen={(cid) => { setId(cid); setTab("units"); }} /> },
          { key: "files", label: <Space><PaperClipOutlined />Tệp đính kèm ({files.length})</Space>, children: <>
            <Space style={{ marginBottom: 12 }} wrap>
              {canUploadDoc && <Upload showUploadList={false} customRequest={doUpload()} accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.zip">
                <Button icon={<UploadOutlined />}>Đính kèm văn bản giao</Button></Upload>}
              {canUploadReport && <Upload showUploadList={false} customRequest={doUpload(myAssignment.id)} accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.zip">
                <Button icon={<UploadOutlined />} type="primary" ghost>Đính kèm báo cáo của {myAssignment.unit_name}</Button></Upload>}
            </Space>
            <Table size="small" rowKey="id" pagination={false} dataSource={files} locale={{ emptyText: "Chưa có tệp" }} columns={[
              { title: "Loại", dataIndex: "kind", width: 120, render: (v) => v === "van_ban" ? <Tag color="blue">Văn bản giao</Tag> : <Tag color="green">Báo cáo</Tag> },
              { title: "Tên tệp", dataIndex: "file_name", render: (v, x: any) => <a onClick={() => dl(x)}><PaperClipOutlined /> {v}</a> },
              { title: "Đơn vị", dataIndex: "assignment_id", render: (v) => v ? t.assignments.find((a: any) => a.id === v)?.unit_name ?? "—" : t.assigner_name },
              { title: "Dung lượng", dataIndex: "size", width: 100, render: (v) => `${(v / 1024).toFixed(1)} KB` },
              { title: "Thời gian", dataIndex: "created_at", width: 140, render: (v) => dayjs(v).format("HH:mm DD/MM/YY") },
            ]} />
          </> },
          { key: "log", label: "Lịch sử xử lý", children: <Timeline items={t.logs.map((l: any) => ({
            color: ["xac_nhan", "phat_hanh"].includes(l.action) ? "green" : ["tra_lai", "khong_tiep_nhan"].includes(l.action) ? "red" : l.action === "giao_tiep" ? "purple" : "blue",
            children: <div><b>{ACTION_NAMES[l.action] ?? l.action}</b> <span className="muted">· {l.user ?? "Hệ thống"} · {dayjs(l.created_at).format("HH:mm DD/MM/YYYY")}</span><div>{l.note}</div></div> }))} /> },
        ]} />
      </>}
      {act && <ActionModal a={act.a} action={act.action} onClose={() => setAct(null)} onDone={() => { setAct(null); load(); onChanged(); }} />}
      {cascadeFor && <CascadeModal a={cascadeFor} task={t} onClose={() => setCascadeFor(null)}
        onDone={() => { setCascadeFor(null); load(); onChanged(); }} />}
    </Drawer>
  );
}

function CreateTask({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [form] = Form.useForm();
  const [units, setUnits] = useState<any[]>([]);
  useEffect(() => { api.get("/units", { params: { size: 500 } }).then((r) => setUnits(r.data.items)); }, []);
  const submit = async () => {
    const v = await form.validateFields();
    await api.post("/tasks", { ...v, deadline: v.deadline.format("YYYY-MM-DD"), doc_date: v.doc_date?.format("YYYY-MM-DD") });
    onDone();
  };
  const opts = units.map((u) => ({ value: u.id, label: `${u.name} (${u.region_name})` }));
  const pick = (cat: string) => form.setFieldValue("lead_unit_ids", units.filter((u) => u.category === cat || (cat === "gd" && u.unit_type === "giao_duc")).map((u) => u.id));
  return (
    <Modal open width={760} title="Giao nhiệm vụ mới (phát hành văn bản chỉ đạo)" onCancel={onClose} onOk={submit} okText="Phát hành & giao" okButtonProps={{ icon: <SendOutlined /> }}>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Mô hình 2 cấp: giao cho UBND xã/phường, xã sẽ giao tiếp xuống trường học trên địa bàn và tổng hợp báo cáo lên. Có thể giao thẳng cho trường THPT (do Sở GD&ĐT quản lý)." />
      <Form form={form} layout="vertical" initialValues={{ priority: "thuong", doc_type: "cong_van", doc_date: dayjs() }}>
        <Form.Item name="title" label="Trích yếu / tên nhiệm vụ" rules={[{ required: true }]}><Input /></Form.Item>
        <Row gutter={12}>
          <Col span={8}><Form.Item name="doc_number" label="Số/ký hiệu văn bản"><Input placeholder="123/UBND-VX" /></Form.Item></Col>
          <Col span={8}><Form.Item name="doc_date" label="Ngày văn bản"><DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" /></Form.Item></Col>
          <Col span={8}><Form.Item name="deadline" label="Hạn xử lý" rules={[{ required: true }]}><DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" disabledDate={(d) => d.isBefore(dayjs(), "day")} /></Form.Item></Col>
          <Col span={8}><Form.Item name="doc_type" label="Loại văn bản"><Select options={[{ value: "cong_van", label: "Công văn" }, { value: "ke_hoach", label: "Kế hoạch" }, { value: "quyet_dinh", label: "Quyết định" }]} /></Form.Item></Col>
          <Col span={8}><Form.Item name="priority" label="Độ khẩn"><Select options={[{ value: "thuong", label: "Thường" }, { value: "khan", label: "Khẩn" }]} /></Form.Item></Col>
          <Col span={8}><Form.Item name="pillar_code" label="Trụ cột CĐS liên quan"><Select allowClear options={Object.entries(PILLAR_NAMES).map(([value, label]) => ({ value, label }))} /></Form.Item></Col>
        </Row>
        <Form.Item name="content" label="Nội dung chỉ đạo"><Input.TextArea rows={2} /></Form.Item>
        <Form.Item label={<Space>Đơn vị chủ trì
          <Button size="small" onClick={() => pick("ubnd_xa")}>Tất cả UBND xã/phường</Button>
          <Button size="small" onClick={() => pick("thpt")}>Tất cả trường THPT</Button></Space>} name="lead_unit_ids" rules={[{ required: true, message: "Chọn đơn vị chủ trì" }]}>
          <Select mode="multiple" showSearch optionFilterProp="label" options={opts} maxTagCount={6} />
        </Form.Item>
        <Form.Item name="coord_unit_ids" label="Đơn vị phối hợp"><Select mode="multiple" showSearch optionFilterProp="label" options={opts} maxTagCount={6} /></Form.Item>
      </Form>
    </Modal>
  );
}

export default function Tasks() {
  const { can } = useAuth();
  const [box, setBox] = useState("all");
  const [f, setF] = useState<any>({ page: 1, size: 15, level: "goc" });
  const [data, setData] = useState<any>({ total: 0, items: [] });
  const [stats, setStats] = useState<any>();
  const [params, setParams] = useSearchParams();
  const [detail, setDetail] = useState<number | null>(params.get("open") ? Number(params.get("open")) : null);
  useEffect(() => { const o = params.get("open"); if (o) { setDetail(Number(o)); setParams({}, { replace: true }); } }, [params]);
  const [creating, setCreating] = useState(false);
  const load = () => {
    api.get("/tasks", { params: { ...f, box, level: f.level || undefined } }).then((r) => setData(r.data));
    api.get("/tasks/stats").then((r) => setStats(r.data));
  };
  useEffect(load, [f, box]);

  return (
    <>
      <PageHeader title="Giao & theo dõi nhiệm vụ" sub="Liên thông 3 cấp: UBND tỉnh / Sở → UBND xã, phường → trường học → báo cáo ngược lên → xác nhận"
        extra={can("task.assign") && <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>Giao nhiệm vụ</Button>} />
      <Card size="small" style={{ marginBottom: 16 }}>
        <Steps size="small" items={[
          { title: "Tỉnh/Sở giao", description: "Phát hành văn bản đến UBND xã" }, { title: "Xã tiếp nhận", description: "Văn thư → lãnh đạo → phòng" },
          { title: "Xã giao tiếp", description: "Xuống trường MN, TH, THCS" }, { title: "Trường báo cáo", description: "Xã kiểm tra, xác nhận" },
          { title: "Xã tổng hợp báo cáo", description: "Khi các trường đã xong" }, { title: "Tỉnh xác nhận", description: "Đóng nhiệm vụ" },
        ]} />
      </Card>
      {stats && <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {stats.by_status.map((s: any) => (
          <Col xs={12} md={8} xl={4} key={s.status}>
            <Card size="small" hoverable onClick={() => setF({ ...f, status: f.status === s.status ? undefined : s.status, page: 1 })}
              style={{ outline: f.status === s.status ? "2px solid #1d4ed8" : undefined }}>
              <Badge status={TASK_STATUS[s.status] as any} text={s.name} /><div style={{ fontSize: 24, fontWeight: 700 }}>{s.count}</div>
            </Card>
          </Col>
        ))}
      </Row>}
      <Card size="small">
        <Tabs activeKey={box} onChange={(k) => { setBox(k); setF({ ...f, page: 1 }); }} items={[
          { key: "all", label: "Tất cả" }, { key: "nhan", label: "Nhiệm vụ được giao (nhận)" }, { key: "giao", label: "Nhiệm vụ đã giao" },
        ]} tabBarExtraContent={<Space>
          <Segmented value={f.level} onChange={(v) => setF({ ...f, level: v, page: 1 })}
            options={[{ label: "Nhiệm vụ gốc", value: "goc" }, { label: "Giao tiếp", value: "giao_tiep" }, { label: "Tất cả", value: "" }]} />
          <Input.Search allowClear placeholder="Tìm trích yếu, số văn bản" style={{ width: 240 }} onSearch={(q) => setF({ ...f, q, page: 1 })} />
        </Space>} />
        <Table rowKey="id" size="middle" dataSource={data.items} onRow={(t: any) => ({ onClick: () => setDetail(t.id), style: { cursor: "pointer" } })}
          pagination={{ current: f.page, pageSize: f.size, total: data.total, onChange: (page, size) => setF({ ...f, page, size }) }}
          columns={[
            { title: "Mã", dataIndex: "code", width: 120 },
            { title: "Trích yếu", dataIndex: "title", render: (v, t: any) => <div>{t.is_cascaded && <Tag color="purple">Giao tiếp</Tag>}<b>{v}</b> {t.priority === "khan" && <Tag color="red">Khẩn</Tag>}<div className="muted" style={{ fontSize: 12 }}>{t.doc_number} · {t.assigner_name}</div></div> },
            { title: "Hạn", dataIndex: "deadline", width: 110, render: (v) => <span style={{ color: dayjs(v).isBefore(dayjs(), "day") ? "#dc2626" : undefined }}>{fmt(v)}</span> },
            { title: "Hoàn thành", key: "p", width: 170, render: (_, t: any) => <Progress size="small" percent={t.total_units ? Math.round((t.done_units * 100) / t.total_units) : 0} format={() => `${t.done_units}/${t.total_units}`} /> },
            { title: "Đã giao tiếp", dataIndex: "cascaded_units", width: 100, align: "right", render: (v, t: any) => v ? <Tag color="purple">{v}/{t.total_units}</Tag> : "—" },
            { title: "Quá hạn", dataIndex: "overdue_units", width: 80, align: "right", render: (v) => v ? <Tag color="red">{v}</Tag> : "—" },
            { title: "Trạng thái tại đơn vị bạn", key: "s", width: 190, responsive: ["lg"], render: (_, t: any) => t.assignments.length <= 3
              ? <Space direction="vertical" size={0}>{t.assignments.map((a: any) => <Badge key={a.id} status={TASK_STATUS[a.status] as any} text={a.status_name} />)}</Space>
              : <span className="muted">{t.assignments.length} đơn vị</span> },
          ]} />
      </Card>
      {detail && <TaskDetail id={detail} onClose={() => setDetail(null)} onChanged={load} />}
      {creating && <CreateTask onClose={() => setCreating(false)} onDone={() => { setCreating(false); load(); }} />}
    </>
  );
}
