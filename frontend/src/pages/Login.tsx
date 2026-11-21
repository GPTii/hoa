import { useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Tag, Tooltip, Typography } from "antd";
import { api } from "../api";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

const LEVELS = ["tinh", "so", "xa", "truong", "khac", "he_thong"];
const LEVEL_COLOR: Record<string, string> = { he_thong: "default", tinh: "red", so: "purple", xa: "blue", truong: "green", khac: "gold" };

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState<any[]>([]);
  const [cfg, setCfg] = useState<any>({});
  const [reason, setReason] = useState<string | null>(() => { const r = sessionStorage.getItem("dti_logout_reason"); sessionStorage.removeItem("dti_logout_reason"); return r; });
  useEffect(() => { api.get("/auth/public-config").then((r) => setCfg(r.data)); }, []);
  useEffect(() => {
    // chỉ ở chế độ demo: danh sách tài khoản mẫu (không lộ quyền, cấu hình)
    api.get("/auth/demo-accounts").then((r) => setRoles(r.data.map((d: any) => ({ level: d.level, level_name: d.level_name, name: d.role_name,
      demo_users: [{ username: d.username, full_name: d.role_name }] }))));
  }, []);
  const submit = async (v: { username: string; password: string }) => {
    setLoading(true);
    try { await login(v.username, v.password); nav("/"); } finally { setLoading(false); }
  };
  return (
    <div className="login-bg">
      <div className="login-left">
        <Typography.Text style={{ color: "#93c5fd", letterSpacing: 1 }}>{(cfg.system_name || "NỀN TẢNG TRÍ TUỆ DỮ LIỆU").toUpperCase()}</Typography.Text>
        <Typography.Title style={{ color: "#fff", marginTop: 8 }}>Hỗ trợ quản trị chuyển đổi số<br />cho cơ quan hành chính & cơ sở giáo dục</Typography.Title>
        <Typography.Paragraph style={{ color: "#cbd5e1", fontSize: 15, maxWidth: 560 }}>
          {cfg.province_label ? `${cfg.province_label} – ` : ""}Mô hình chính quyền địa phương 2 cấp (Tỉnh → Xã/Phường). Tích hợp dữ liệu, đánh giá
          Digital Transformation Score, cảnh báo, đề xuất giải pháp và theo dõi nhiệm vụ liên thông.
        </Typography.Paragraph>
        <div className="flow">
          {["Dữ liệu nguồn", "Bronze", "Silver", "Gold", "DTI Score", "Cảnh báo", "Đề xuất", "Hoạch định"].map((s) => <span key={s}>{s}</span>)}
        </div>
      </div>
      <div className="login-right">
        <Card style={{ width: "100%", maxWidth: 400 }} bordered={false}>
          <Typography.Title level={3} style={{ marginBottom: 0 }}>Đăng nhập</Typography.Title>
          {cfg.org_name && <Typography.Text type="secondary">{cfg.org_name}</Typography.Text>}
          {reason && <Alert type="warning" showIcon style={{ margin: "12px 0 0" }} message={reason} closable onClose={() => setReason(null)} />}
          <div style={{ height: 16 }} />
          <Form form={form} layout="vertical" onFinish={submit} initialValues={{ username: "admin", password: "123456" }}>
            <Form.Item name="username" label="Tên đăng nhập" rules={[{ required: true }]}><Input prefix={<UserOutlined />} size="large" /></Form.Item>
            <Form.Item name="password" label="Mật khẩu" rules={[{ required: true }]}><Input.Password prefix={<LockOutlined />} size="large" /></Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={loading}>Đăng nhập</Button>
          </Form>
          <div className="demo-accounts" style={{ marginTop: 24 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>Tài khoản thử nghiệm theo cấp × chức danh (mật khẩu 123456) – bấm để điền:</Typography.Text>
            {cfg.demo_mode === false ? null : LEVELS.map((lv) => {
              const rs = roles.filter((r) => r.level === lv && r.demo_users.length);
              if (!rs.length) return null;
              return (
                <div key={lv} style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase" }}>{rs[0].level_name}</div>
                  {rs.flatMap((r) => r.demo_users.slice(0, 1).map((u: any) => (
                    <Tooltip key={u.username} title={`${u.username} · ${u.full_name}`}>
                      <Tag color={LEVEL_COLOR[lv]} onClick={() => form.setFieldsValue({ username: u.username, password: "123456" })}>{r.name}</Tag>
                    </Tooltip>)))}
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
