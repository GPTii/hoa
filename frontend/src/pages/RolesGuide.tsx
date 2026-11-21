import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Collapse, Empty, Row, Space, Steps, Table, Tag, Tooltip, Typography } from "antd";
import { CheckCircleTwoTone, CloseCircleOutlined, EyeOutlined, UserOutlined } from "@ant-design/icons";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/common";

const LEVEL_ORDER = ["tinh", "so", "xa", "truong", "khac", "he_thong"];
const LEVEL_COLOR: Record<string, string> = { he_thong: "#475569", tinh: "#b91c1c", so: "#7c3aed", xa: "#1d4ed8", truong: "#059669", khac: "#ca8a04" };
const TASK_PERMS = ["task.assign", "task.confirm", "task.receive", "task.dispatch", "task.process", "task.sign"];
const TASK_LABEL: Record<string, string> = {
  "task.assign": "Giao / giao tiếp", "task.confirm": "Xác nhận", "task.receive": "Tiếp nhận", "task.dispatch": "Phân công",
  "task.process": "Xử lý, trình", "task.sign": "Ký & gửi BC",
};

export default function RolesGuide() {
  const { user, impersonate } = useAuth();
  const [roles, setRoles] = useState<any[]>([]);
  useEffect(() => { api.get("/auth/roles-guide").then((r) => setRoles(r.data)); }, []);
  const groups = LEVEL_ORDER.map((lv) => ({ lv, items: roles.filter((r) => r.level === lv) })).filter((g) => g.items.length);

  const LoginBtn = ({ u }: { u: any }) => (
    <Tooltip title={`${u.full_name}${u.unit ? " – " + u.unit : ""}`}>
      <Button size="small" icon={<EyeOutlined />} disabled={u.username === user?.username} onClick={() => impersonate(u.id)}>
        {u.username === user?.username ? "Tài khoản của bạn" : `Xem dưới vai trò · ${u.username}`}
      </Button>
    </Tooltip>
  );

  return (
    <>
      <PageHeader title="Vai trò & chức năng" sub="Mỗi người dùng = Cấp (tỉnh / sở / xã / trường) × Chức danh → được xem dữ liệu nào, được làm thao tác nào" />
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message={<>Chỉ quản trị hệ thống thấy trang này. Bấm <b>"Xem dưới vai trò"</b> để mở giao diện, menu, dữ liệu đúng như người dùng đó thấy (chế độ chỉ xem); bấm <b>"Trở về quản trị"</b> trên thanh màu cam để quay lại.</>} />

      <Card size="small" title="Một văn bản đi qua những ai? (ví dụ phường Khánh Hậu)" style={{ marginBottom: 16 }}>
        <Steps size="small" labelPlacement="vertical" items={[
          { title: "Lãnh đạo UBND tỉnh", description: "Giao nhiệm vụ" },
          { title: "Văn thư phường", description: "Tiếp nhận văn bản" },
          { title: "Chủ tịch phường", description: "Phân công phòng, giao tiếp xuống trường" },
          { title: "Trưởng phòng VH-XH", description: "Phân công công chức" },
          { title: "Hiệu trưởng / GV", description: "Trường xử lý, báo cáo lên phường" },
          { title: "Công chức phường", description: "Tổng hợp, trình dự thảo" },
          { title: "Chủ tịch phường", description: "Duyệt, ký số gửi tỉnh" },
          { title: "VP UBND tỉnh", description: "Kiểm tra, xác nhận" },
        ]} />
      </Card>

      {groups.map(({ lv, items }) => (
        <div key={lv} style={{ marginBottom: 20 }}>
          <Typography.Title level={5} style={{ borderLeft: `4px solid ${LEVEL_COLOR[lv]}`, paddingLeft: 8 }}>{items[0].level_name}</Typography.Title>
          <Row gutter={[16, 16]}>
            {items.map((r) => (
              <Col xs={24} md={12} xl={8} key={r.code}>
                <Card size="small" style={{ height: "100%", borderTop: `3px solid ${LEVEL_COLOR[lv]}`, background: r.code === user?.role.code ? "#eff6ff" : undefined }}
                  title={<Space><UserOutlined />{r.name}</Space>}>
                  <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>{r.description}</Typography.Paragraph>
                  <div style={{ fontSize: 12, marginBottom: 8 }}>Phạm vi dữ liệu: <Tag color="blue">{r.scope_name}</Tag></div>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Vào hệ thống để làm gì</div>
                  <ul style={{ paddingLeft: 18, margin: "0 0 8px" }}>{r.duties.map((d: string) => <li key={d} style={{ fontSize: 13 }}>{d}</li>)}</ul>
                  <div style={{ marginBottom: 8 }}>
                    {TASK_PERMS.map((p) => <Tag key={p} color={r.permissions.includes(p) ? "green" : undefined} style={{ opacity: r.permissions.includes(p) ? 1 : 0.45 }}>
                      {r.permissions.includes(p) ? "✓" : "✕"} {TASK_LABEL[p]}</Tag>)}
                  </div>
                  <Collapse size="small" ghost items={[{ key: "1", label: `Chi tiết quyền (${r.can.length} được / ${r.cannot.length} không)`, children: (
                    <Row gutter={8}>
                      <Col span={12}>{r.can.map((c: string) => <div key={c} style={{ fontSize: 12 }}><CheckCircleTwoTone twoToneColor="#16a34a" /> {c}</div>)}</Col>
                      <Col span={12}>{r.cannot.map((c: string) => <div key={c} style={{ fontSize: 12, color: "#94a3b8" }}><CloseCircleOutlined /> {c}</div>)}</Col>
                    </Row>) }]} />
                  <Space wrap style={{ marginTop: 8 }}>{r.demo_users.length ? r.demo_users.map((u: any) => <LoginBtn key={u.username} u={u} />) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có tài khoản" />}</Space>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      ))}

      <Card size="small" title="Ma trận thao tác nhiệm vụ theo vai trò">
        <Table size="small" rowKey="code" pagination={false} scroll={{ x: 900 }} dataSource={roles} columns={[
          { title: "Vai trò", dataIndex: "name", fixed: "left", width: 230, render: (v, r: any) => <div>{v}<div className="muted" style={{ fontSize: 11 }}>{r.level_name} · {r.scope_name}</div></div> },
          ...TASK_PERMS.map((p) => ({ title: TASK_LABEL[p], key: p, align: "center" as const, width: 100,
            render: (_: any, r: any) => r.permissions.includes(p) ? <CheckCircleTwoTone twoToneColor="#16a34a" /> : <span style={{ color: "#cbd5e1" }}>—</span> })),
          { title: "Nhập dữ liệu", key: "di", align: "center", width: 100, render: (_, r: any) => r.permissions.includes("data.import") ? <CheckCircleTwoTone twoToneColor="#16a34a" /> : <span style={{ color: "#cbd5e1" }}>—</span> },
          { title: "Quản trị", key: "ad", align: "center", width: 90, render: (_, r: any) => r.permissions.includes("user.manage") ? <CheckCircleTwoTone twoToneColor="#16a34a" /> : <span style={{ color: "#cbd5e1" }}>—</span> },
        ]} />
      </Card>
    </>
  );
}
