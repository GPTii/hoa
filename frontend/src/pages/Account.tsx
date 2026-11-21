import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Descriptions, Form, Input, List, Popconfirm, Row, Tag, Typography, message } from "antd";
import { DesktopOutlined, LockOutlined, LogoutOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/common";

const ua = (s?: string) => !s ? "Không rõ" : /Edg/.test(s) ? "Microsoft Edge" : /Chrome/.test(s) ? "Google Chrome" : /Firefox/.test(s) ? "Firefox" : /python|urllib/i.test(s) ? "Ứng dụng / API" : s.slice(0, 40);

/** Form đổi mật khẩu dùng chung (theo chính sách mật khẩu do quản trị cấu hình) */
function ChangePasswordForm({ onDone }: { onDone?: () => void }) {
  const [form] = Form.useForm();
  const [policy, setPolicy] = useState<any>({ password_min_length: 6 });
  useEffect(() => { api.get("/auth/public-config").then((r) => setPolicy(r.data)); }, []);
  const submit = async () => {
    const v = await form.validateFields();
    await api.post("/auth/change-password", { old_password: v.old_password, new_password: v.new_password });
    message.success("Đã đổi mật khẩu – các thiết bị khác đã được đăng xuất");
    form.resetFields();
    onDone?.();
  };
  return (
    <Form form={form} layout="vertical" onFinish={submit}>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        Yêu cầu: tối thiểu {policy.password_min_length} ký tự{policy.password_require_complex ? ", có chữ hoa, chữ thường, chữ số và ký tự đặc biệt" : ""}.
      </Typography.Paragraph>
      <Form.Item name="old_password" label="Mật khẩu hiện tại" rules={[{ required: true }]}><Input.Password /></Form.Item>
      <Form.Item name="new_password" label="Mật khẩu mới" rules={[{ required: true, min: policy.password_min_length, message: `Tối thiểu ${policy.password_min_length} ký tự` }]}><Input.Password /></Form.Item>
      <Form.Item name="confirm" label="Nhập lại mật khẩu mới" dependencies={["new_password"]} rules={[{ required: true },
        ({ getFieldValue }) => ({ validator: (_, v) => v === getFieldValue("new_password") ? Promise.resolve() : Promise.reject(new Error("Mật khẩu nhập lại không khớp")) })]}>
        <Input.Password /></Form.Item>
      <Button type="primary" htmlType="submit">Đổi mật khẩu</Button>
    </Form>
  );
}

/** Màn hình bắt buộc đổi mật khẩu: tài khoản mới, mật khẩu tạm do quản trị cấp, hoặc mật khẩu hết hạn */
export function ForceChangePassword() {
  const { user, logout, passwordChanged } = useAuth();
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "linear-gradient(160deg,#0b1f44,#1d4ed8)", padding: 16 }}>
      <Card style={{ width: "100%", maxWidth: 440 }} title={<><LockOutlined /> Đổi mật khẩu để tiếp tục</>}
        extra={<Button type="link" onClick={logout}>Đăng xuất</Button>}>
        <Alert type="warning" showIcon style={{ marginBottom: 16 }}
          message={`Xin chào ${user?.full_name}`}
          description="Bạn đang dùng mật khẩu tạm / tài khoản mới cấp hoặc mật khẩu đã hết hạn. Vui lòng đặt mật khẩu mới để bảo vệ tài khoản." />
        <ChangePasswordForm onDone={() => { passwordChanged(); location.href = "/"; }} />
      </Card>
    </div>
  );
}

/** Trang cá nhân: mỗi người chỉ thấy thông tin, vai trò và phiên đăng nhập CỦA CHÍNH MÌNH. */
export default function Account() {
  const { user, impersonatedBy } = useAuth();
  const [r, setR] = useState<any>();
  const [sessions, setSessions] = useState<any[]>([]);
  const loadSessions = () => api.get("/auth/my-sessions").then((x) => setSessions(x.data));
  useEffect(() => { api.get("/auth/my-role").then((x) => setR(x.data)); loadSessions(); }, []);

  return (
    <>
      <PageHeader title="Tài khoản của tôi" sub="Thông tin cá nhân, vai trò được giao, thiết bị đăng nhập và đổi mật khẩu" />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card size="small" title="Thông tin tài khoản">
            <Descriptions size="small" layout="vertical" column={{ xs: 1, sm: 2 }} items={[
              { label: "Họ tên", children: <b>{user?.full_name}</b> }, { label: "Tên đăng nhập", children: user?.username },
              { label: "Chức vụ", children: user?.position }, { label: "Đơn vị", children: user?.unit?.name ?? "—" },
            ]} />
          </Card>
          {r && <Card size="small" title={<>Vai trò: <Tag color="blue">{r.name}</Tag></>} style={{ marginTop: 16 }}>
            <Typography.Paragraph type="secondary">{r.description}</Typography.Paragraph>
            <Alert type="info" showIcon style={{ marginBottom: 12 }}
              message={<>Cấp: <b>{r.level_name}</b> · Phạm vi dữ liệu: <b>{r.scope_name}</b>{r.scope_detail ? ` (${r.scope_detail})` : ""}</>}
              description="Bạn chỉ xem được dữ liệu và thực hiện được thao tác trong phạm vi này. Cần thêm quyền, liên hệ quản trị hệ thống của đơn vị." />
            <Typography.Title level={5}>Công việc bạn phụ trách</Typography.Title>
            <List size="small" dataSource={r.duties} renderItem={(d: string) => <List.Item>• {d}</List.Item>} />
          </Card>}
        </Col>
        <Col xs={24} lg={10}>
          {!impersonatedBy && <Card size="small" title={<><LockOutlined /> Đổi mật khẩu</>}>
            <ChangePasswordForm onDone={loadSessions} />
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12 }}>
              Quên mật khẩu: liên hệ quản trị hệ thống của xã/phường hoặc của tỉnh để được cấp mật khẩu tạm.
            </Typography.Paragraph>
          </Card>}
          <Card size="small" title={<><DesktopOutlined /> Thiết bị đang đăng nhập</>} style={{ marginTop: 16 }}
            extra={sessions.length > 1 && !impersonatedBy && <Popconfirm title="Đăng xuất tất cả thiết bị khác?"
              onConfirm={() => api.post("/auth/my-sessions/revoke-others").then((x) => { message.success(`Đã đăng xuất ${x.data.revoked} thiết bị`); loadSessions(); })}>
              <Button size="small" icon={<LogoutOutlined />}>Đăng xuất thiết bị khác</Button></Popconfirm>}>
            <List size="small" dataSource={sessions} renderItem={(s: any) => <List.Item>
              <div><b>{ua(s.user_agent)}</b> {s.current && <Tag color="green">Thiết bị này</Tag>}
                <div className="muted" style={{ fontSize: 12 }}>IP {s.ip} · đăng nhập {dayjs(s.created_at).format("HH:mm DD/MM")} · hoạt động {dayjs(s.last_seen).format("HH:mm DD/MM")}</div></div>
            </List.Item>} />
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 0 }}>Thấy thiết bị lạ? Đổi mật khẩu ngay – mọi thiết bị khác sẽ bị đăng xuất.</Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </>
  );
}
