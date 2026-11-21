/** Thiết lập hệ thống cho một tỉnh mới – hướng dẫn từng bước, trạng thái tự kiểm tra */
import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Collapse, Form, Input, Progress, Row, Select, Space, Steps, Table, Tag, Typography, Upload, message } from "antd";
import { CheckCircleFilled, ClockCircleOutlined, CloudUploadOutlined, DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { api, download } from "../api";
import { useSysConfig } from "../sysconfig";

export function CatalogImportModalBody({ onDone }: { onDone?: () => void }) {
  const [file, setFile] = useState<File>();
  const [res, setRes] = useState<any>();
  const [busy, setBusy] = useState(false);
  const run = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await api.post(`/admin/catalog/import?dry_run=${dry}`, fd);
      setRes(r.data);
      if (!dry) { message.success("Đã nhập danh mục"); onDone?.(); }
    } finally { setBusy(false); }
  };
  const errs = res ? [...res.regions.errors, ...res.units.errors] : [];
  return (
    <>
      <Space wrap style={{ marginBottom: 8 }}>
        <Button icon={<DownloadOutlined />} onClick={() => download("/admin/catalog/template.xlsx", {}, "mau_danh_muc_tinh.xlsx")}>Tải file mẫu</Button>
        <Upload beforeUpload={(f) => { setFile(f); setRes(undefined); return false; }} maxCount={1} accept=".xlsx,.xls" showUploadList={{ showRemoveIcon: false }}>
          <Button icon={<CloudUploadOutlined />}>Chọn file danh mục</Button></Upload>
        <Button disabled={!file} loading={busy} onClick={() => run(true)}>Kiểm tra</Button>
        <Button type="primary" disabled={!res?.dry_run} loading={busy} onClick={() => run(false)}>Nhập vào hệ thống</Button>
      </Space>
      {res && <Alert type={errs.length ? "warning" : "success"} showIcon style={{ marginTop: 8 }}
        message={`${res.dry_run ? "Kết quả kiểm tra" : "Đã nhập"}: địa bàn ${res.regions.new} mới / ${res.regions.update} cập nhật · đơn vị ${res.units.new} mới / ${res.units.update} cập nhật`}
        description={errs.length ? <ul style={{ margin: 0, paddingLeft: 18, maxHeight: 160, overflow: "auto" }}>{errs.map((e: string) => <li key={e}>{e}</li>)}</ul> : "Không có lỗi"} />}
    </>
  );
}

function ProvinceForm({ onDone }: { onDone: () => void }) {
  const [form] = Form.useForm();
  const { reload } = useSysConfig();
  useEffect(() => {
    api.get("/admin/settings").then((r) => form.setFieldsValue(Object.fromEntries(r.data.filter((x: any) => x.group === "tinh").map((x: any) => [x.key, x.value]))));
  }, []);
  const save = async () => {
    await api.put("/admin/settings", await form.validateFields());
    message.success("Đã lưu thông tin tỉnh"); reload(); onDone();
  };
  return (
    <Form form={form} layout="vertical" style={{ maxWidth: 640 }}>
      <Row gutter={12}>
        <Col span={8}><Form.Item name="province_type" label="Loại"><Select options={[{ value: "Tỉnh", label: "Tỉnh" }, { value: "Thành phố", label: "Thành phố" }]} /></Form.Item></Col>
        <Col span={16}><Form.Item name="province_name" label="Tên tỉnh/thành phố" rules={[{ required: true }]}><Input placeholder="VD: Tây Ninh" /></Form.Item></Col>
        <Col span={12}><Form.Item name="system_name" label="Tên hệ thống"><Input /></Form.Item></Col>
        <Col span={12}><Form.Item name="system_subtitle" label="Mô tả ngắn"><Input /></Form.Item></Col>
        <Col span={24}><Form.Item name="org_name" label="Đơn vị chủ quản vận hành"><Input placeholder="VD: Sở Khoa học và Công nghệ tỉnh …" /></Form.Item></Col>
      </Row>
      <Button type="primary" onClick={save}>Lưu thông tin tỉnh</Button>
    </Form>
  );
}

const GUIDE: Record<string, { who: string; how: JSX.Element }> = {
  province: { who: "Quản trị hệ thống", how: <>Đặt tên tỉnh/thành phố, tên hệ thống và đơn vị chủ quản. Toàn bộ giao diện (logo, trang đăng nhập, báo cáo) tự hiển thị theo thông tin này – không cần sửa mã nguồn.</> },
  catalog: { who: "Quản trị hệ thống", how: <>Tải file mẫu → điền <b>sheet dia_ban</b> (danh sách xã, phường, đặc khu theo nghị quyết sắp xếp của tỉnh) và <b>sheet don_vi</b> (UBND tỉnh, Văn phòng, các Sở, UBND xã, trường học) → <b>Kiểm tra</b> → <b>Nhập</b>. Nhập lại cùng mã sẽ cập nhật, không tạo trùng. Sửa lẻ tại <Link to="/admin/units">Danh mục đơn vị</Link> / <Link to="/admin/regions">Danh mục địa bàn</Link>.</> },
  period: { who: "Quản trị hệ thống", how: <>Hệ thống đã tạo sẵn các quý gần nhất. Kiểm tra <b>kỳ hiện hành</b> đúng quý đang đánh giá tại <Link to="/admin/periods">Kỳ đánh giá</Link>; khi công bố kết quả một quý, <b>khóa số liệu</b> quý đó.</> },
  criteria: { who: "Chuyên viên dữ liệu (Sở KH&CN)", how: <>Bộ 7 trụ cột / 24 tiêu chí mặc định (tham chiếu DTI của Bộ TT&TT) đã có sẵn. Theo nguyên tắc tách biệt nhiệm vụ, quản trị không chỉnh tiêu chí: hãy cấp tài khoản vai trò <b>Chuyên viên dữ liệu Sở KH&CN</b>, người này vào <i>Bộ tiêu chí DTI</i> để điều chỉnh trọng số, mục tiêu cho phù hợp tỉnh (tổng trọng số trụ cột = 100).</> },
  accounts: { who: "Quản trị hệ thống → Quản trị xã", how: <>Thứ tự khuyến nghị: (1) Lãnh đạo UBND tỉnh, Văn phòng UBND tỉnh, Chuyên viên dữ liệu Sở KH&CN, Lãnh đạo Sở GD&ĐT; (2) <b>mỗi xã/phường một tài khoản "Quản trị hệ thống cấp xã"</b> – dùng <Link to="/admin/users">Nhập từ Excel</Link>; (3) quản trị xã tự cấp tài khoản cho văn thư, lãnh đạo, công chức và các trường trên địa bàn. Mọi tài khoản mới phải đổi mật khẩu ở lần đăng nhập đầu.</> },
  security: { who: "Quản trị hệ thống", how: <>Trước khi đưa vào vận hành: <b>tắt chế độ demo</b>, kiểm tra chính sách mật khẩu và khóa đăng nhập tại <Link to="/admin/settings">Tham số & chính sách</Link>; đổi mật khẩu admin tại <Link to="/account">Tài khoản của tôi</Link>; đặt <code>JWT_SECRET</code> riêng trong tệp <code>backend/.env</code>; tạo bản <Link to="/admin/monitor">sao lưu</Link> đầu tiên.</> },
  data: { who: "Chuyên viên dữ liệu (Sở KH&CN)", how: <>Chuyên viên dữ liệu vào <i>Tích hợp dữ liệu</i> → tải file mẫu khảo sát theo loại hình → các đơn vị điền → tải lên (Bronze → Silver → Gold tự chạy). Hoặc cấp <Link to="/admin/api">khóa API</Link> để trục LGSP của tỉnh đẩy số liệu tự động.</> },
};

export default function AdminSetup() {
  const [s, setS] = useState<any>();
  const [open, setOpen] = useState<string[]>([]);
  const load = () => api.get("/admin/setup/status").then((r) => {
    setS(r.data);
    if (!open.length) { const first = r.data.steps.find((x: any) => !x.done); setOpen(first ? [first.key] : []); }
  });
  useEffect(() => { load(); }, []);
  if (!s) return null;
  const pct = Math.round((s.done * 100) / s.total);
  return (
    <>
      <Row gutter={16} align="middle" style={{ marginBottom: 16 }}>
        <Col flex="none"><Progress type="circle" percent={pct} size={90} format={() => `${s.done}/${s.total}`} /></Col>
        <Col flex="auto">
          <Typography.Title level={4} style={{ margin: 0 }}>{s.province || "Chưa cấu hình tỉnh"}</Typography.Title>
          <Typography.Text type="secondary">Hệ thống dùng chung cho mọi tỉnh/thành theo mô hình chính quyền 2 cấp. Làm lần lượt các bước dưới đây để đưa hệ thống vào vận hành cho tỉnh của bạn.</Typography.Text>
          <div><Button size="small" icon={<ReloadOutlined />} style={{ marginTop: 6 }} onClick={load}>Kiểm tra lại</Button></div>
        </Col>
      </Row>
      <Steps direction="vertical" size="small" current={-1} items={s.steps.map((st: any, i: number) => ({
        status: st.done ? "finish" : "wait",
        icon: st.done ? <CheckCircleFilled style={{ color: "#16a34a" }} /> : <ClockCircleOutlined />,
        title: <Space><b>Bước {i + 1}. {st.title}</b>{st.done ? <Tag color="green">Đã xong</Tag> : <Tag color="orange">Cần làm</Tag>}</Space>,
        description: (
          <Collapse size="small" ghost activeKey={open} onChange={(k) => setOpen(k as string[])} items={[{
            key: st.key, label: <span className="muted">{st.detail} · Người thực hiện: {GUIDE[st.key].who}</span>,
            children: <Card size="small">
              <Typography.Paragraph style={{ marginBottom: 12 }}>{GUIDE[st.key].how}</Typography.Paragraph>
              {st.key === "province" && <ProvinceForm onDone={load} />}
              {st.key === "catalog" && <CatalogImportModalBody onDone={load} />}
            </Card>,
          }]} />
        ),
      }))} />
      <Collapse style={{ marginTop: 16 }} items={[{ key: "cli", label: "Dành cho kỹ thuật: khởi tạo hệ thống trống cho tỉnh mới / quay lại bản mẫu Tây Ninh", children: (
        <>
          <Alert type="warning" showIcon style={{ marginBottom: 8 }} message="Các lệnh dưới đây XÓA toàn bộ dữ liệu hiện có – chỉ chạy khi cài mới, nhớ sao lưu trước." />
          <Typography.Paragraph>Hệ thống trống cho tỉnh mới (chỉ có khung: vai trò, bộ tiêu chí, kỳ đánh giá, tài khoản admin):</Typography.Paragraph>
          <Typography.Paragraph copyable code>cd backend; .\.venv\Scripts\python -m scripts.seed --blank --province "Bình Phước" --admin-password "MatKhauManh@2026"</Typography.Paragraph>
          <Typography.Paragraph>Bản mẫu tỉnh Tây Ninh với dữ liệu mô phỏng đầy đủ (để demo, đào tạo):</Typography.Paragraph>
          <Typography.Paragraph copyable code>cd backend; .\.venv\Scripts\python -m scripts.seed</Typography.Paragraph>
          <Typography.Paragraph type="secondary">Hướng dẫn đầy đủ: docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md</Typography.Paragraph>
        </>) }]} />
    </>
  );
}

export function CatalogImportCard() {
  return <Card size="small" title="Nhập danh mục địa bàn & đơn vị từ Excel" style={{ marginBottom: 12 }}><CatalogImportModalBody /></Card>;
}

export { Table };
