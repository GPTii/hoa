import { useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Avatar, Button, Dropdown, Layout, Menu, Spin, Tag, theme } from "antd";
import {
  AimOutlined, AlertOutlined, BookOutlined, FileDoneOutlined, FormOutlined, ApartmentOutlined, AuditOutlined, BarChartOutlined, BulbOutlined, ClusterOutlined,
  DashboardOutlined, DatabaseOutlined, FileExcelOutlined, LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
  ApiOutlined, AppstoreOutlined, CalendarOutlined, RocketOutlined, CloudServerOutlined, DesktopOutlined, EnvironmentOutlined, NotificationOutlined, SettingOutlined,
  EyeOutlined, ProfileOutlined, RollbackOutlined, SafetyCertificateOutlined, ScheduleOutlined, TeamOutlined, TrophyOutlined, UserOutlined,
} from "@ant-design/icons";
import { useAuth } from "./auth";
import { useSysConfig } from "./sysconfig";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Units from "./pages/Units";
import UnitDetail from "./pages/UnitDetail";
import Ranking from "./pages/Ranking";
import Alerts from "./pages/Alerts";
import Planning from "./pages/Planning";
import Clusters from "./pages/Clusters";
import Tasks from "./pages/Tasks";
import DataPipeline from "./pages/DataPipeline";
import Framework from "./pages/Framework";
import AMPortfolio from "./pages/AMPortfolio";
import Reports from "./pages/Reports";
import Admin from "./pages/Admin";
import RolesGuide from "./pages/RolesGuide";
import Workspace from "./pages/Workspace";
import Plans from "./pages/Plans";
import Services from "./pages/Services";
import Account, { ForceChangePassword } from "./pages/Account";
import NotificationBell from "./components/NotificationBell";
import Registers from "./pages/Registers";
import SelfAssessment from "./pages/SelfAssessment";
import Assessments from "./pages/Assessments";

const { Sider, Header, Content } = Layout;

type Item = { key: string; label: string; icon: ReactNode; perm: string[]; group: string };
const MENU: Item[] = [
  { key: "/", label: "Bàn làm việc", icon: <ProfileOutlined />, perm: [], group: "Công việc" },
  { key: "/tasks", label: "Văn bản & nhiệm vụ", icon: <ScheduleOutlined />, perm: ["task.view"], group: "Công việc" },
  { key: "/registers", label: "Sổ văn bản đến / đi", icon: <BookOutlined />, perm: ["task.receive", "task.issue", "task.sign"], group: "Công việc" },
  { key: "/assessment", label: "Tự đánh giá CĐS", icon: <FormOutlined />, perm: ["assess.prepare", "assess.submit"], group: "Công việc" },
  { key: "/dashboard", label: "Tổng quan CĐS", icon: <DashboardOutlined />, perm: ["dashboard.view"], group: "Giám sát" },
  { key: "/units", label: "Đơn vị", icon: <ApartmentOutlined />, perm: ["unit.view"], group: "Giám sát" },
  { key: "/assessments", label: "Thẩm định & công bố", icon: <FileDoneOutlined />, perm: ["assess.review", "assess.publish"], group: "Đánh giá" },
  { key: "/ranking", label: "Xếp hạng & so sánh", icon: <TrophyOutlined />, perm: ["dashboard.view"], group: "Đánh giá" },
  { key: "/alerts", label: "Cảnh báo & ưu tiên", icon: <AlertOutlined />, perm: ["alert.view"], group: "Đánh giá" },
  { key: "/clusters", label: "Phân cụm & dự báo", icon: <ClusterOutlined />, perm: ["ml.run"], group: "Đánh giá" },
  { key: "/planning", label: "Hỗ trợ hoạch định", icon: <BulbOutlined />, perm: ["plan.view"], group: "Hoạch định" },
  { key: "/plans", label: "Kế hoạch cải thiện", icon: <ScheduleOutlined />, perm: ["plan.view"], group: "Hoạch định" },
  { key: "/am", label: "AM Intelligence", icon: <AimOutlined />, perm: ["am.view"], group: "Hoạch định" },
  { key: "/data", label: "Tích hợp dữ liệu", icon: <DatabaseOutlined />, perm: ["data.view", "data.import"], group: "Dữ liệu" },
  { key: "/services", label: "Danh mục dịch vụ số", icon: <AppstoreOutlined />, perm: ["unit.manage", "am.view"], group: "Dữ liệu" },
  { key: "/framework", label: "Bộ tiêu chí DTI", icon: <ProfileOutlined />, perm: ["criteria.manage"], group: "Dữ liệu" },
  { key: "/reports", label: "Báo cáo", icon: <FileExcelOutlined />, perm: ["report.view"], group: "Dữ liệu" },
  // ---- quản trị: mỗi chức năng một mục riêng
  { key: "/admin/setup", label: "Thiết lập tỉnh mới", icon: <RocketOutlined />, perm: ["role.manage"], group: "Triển khai" },
  { key: "/admin/users", label: "Tài khoản người dùng", icon: <UserOutlined />, perm: ["user.manage"], group: "Quản trị tài khoản" },
  { key: "/admin/sessions", label: "Phiên đăng nhập", icon: <DesktopOutlined />, perm: ["user.manage"], group: "Quản trị tài khoản" },
  { key: "/admin/permissions", label: "Vai trò & phân quyền", icon: <SafetyCertificateOutlined />, perm: ["role.manage"], group: "Quản trị tài khoản" },
  { key: "/roles", label: "Ma trận vai trò", icon: <TeamOutlined />, perm: ["role.manage"], group: "Quản trị tài khoản" },
  { key: "/admin/units", label: "Danh mục đơn vị", icon: <ApartmentOutlined />, perm: ["catalog.manage", "user.manage"], group: "Danh mục & cấu hình" },
  { key: "/admin/regions", label: "Danh mục địa bàn", icon: <EnvironmentOutlined />, perm: ["catalog.manage"], group: "Danh mục & cấu hình" },
  { key: "/admin/settings", label: "Tham số & chính sách", icon: <SettingOutlined />, perm: ["role.manage"], group: "Danh mục & cấu hình" },
  { key: "/admin/periods", label: "Kỳ đánh giá", icon: <CalendarOutlined />, perm: ["role.manage"], group: "Danh mục & cấu hình" },
  { key: "/admin/announcements", label: "Thông báo hệ thống", icon: <NotificationOutlined />, perm: ["role.manage"], group: "Vận hành hệ thống" },
  { key: "/admin/monitor", label: "Giám sát & sao lưu", icon: <CloudServerOutlined />, perm: ["role.manage"], group: "Vận hành hệ thống" },
  { key: "/admin/audit", label: "Nhật ký & bảo mật", icon: <AuditOutlined />, perm: ["audit.view"], group: "Vận hành hệ thống" },
  { key: "/admin/api", label: "Tích hợp API", icon: <ApiOutlined />, perm: ["role.manage"], group: "Vận hành hệ thống" },
  { key: "/account", label: "Tài khoản của tôi", icon: <UserOutlined />, perm: [], group: "Cá nhân" },
];

function Shell() {
  const { user, can, logout, impersonatedBy, stopImpersonate } = useAuth();
  const { cfg } = useSysConfig();
  const nav = useNavigate();
  const loc = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { token } = theme.useToken();
  const items = MENU.filter((m) => !m.perm.length || can(...m.perm));
  const groups = [...new Set(items.map((i) => i.group))];
  const active = items.map((i) => i.key).filter((k) => k === "/" ? loc.pathname === "/" : loc.pathname.startsWith(k)).at(-1) ?? "/";
  const scopeText: Record<string, string> = { all: "Toàn tỉnh", giao_duc: "Toàn ngành giáo dục", region: user?.region?.name ?? "Địa bàn", unit: "Đơn vị mình", assigned: "Đơn vị phụ trách" };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={248} collapsible collapsed={collapsed} trigger={null} breakpoint="lg" onBreakpoint={setCollapsed}
        style={{ position: "sticky", top: 0, height: "100vh", overflow: "auto" }}>
        <div className="brand">
          <div className="brand-logo"><BarChartOutlined /></div>
          {!collapsed && <div><div className="brand-title">{cfg.system_name}</div><div className="brand-sub">{cfg.province_label || cfg.system_subtitle}</div></div>}
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[active]} onClick={(e) => nav(e.key)}
          items={groups.map((g) => ({ type: "group", key: g, label: collapsed ? null : g,
            children: items.filter((i) => i.group === g).map((i) => ({ key: i.key, icon: i.icon, label: i.label })) }))} />
      </Sider>
      <Layout>
        <Header style={{ padding: "0 20px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${token.colorBorderSecondary}`, position: "sticky", top: 0, zIndex: 10 }}>
          <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} />
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <NotificationBell />
            <Tag color="blue" icon={<TeamOutlined />} style={{ cursor: "pointer" }} onClick={() => nav("/account")}>{user?.role.name}</Tag>
            <Tag icon={<AuditOutlined />}>Phạm vi: {scopeText[user?.role.data_scope ?? "unit"]}</Tag>
            <Dropdown menu={{ items: [
              { key: "u", label: <div><b>{user?.full_name}</b><div className="muted" style={{ fontSize: 12 }}>{user?.unit?.name ?? user?.position}</div></div>, disabled: true },
              { type: "divider" },
              { key: "acc", icon: <UserOutlined />, label: "Tài khoản của tôi", onClick: () => nav("/account") },
              ...(can("role.manage") && !impersonatedBy ? [{ key: "imp", icon: <EyeOutlined />, label: "Xem dưới vai trò khác…", onClick: () => nav("/roles") }] : []),
              ...(impersonatedBy ? [{ key: "back", icon: <RollbackOutlined />, label: "Trở về quản trị", onClick: stopImpersonate }] : []),
              { key: "logout", icon: <LogoutOutlined />, label: "Đăng xuất", onClick: logout },
            ] }}>
              <Button type="text" style={{ height: 48 }}><Avatar size="small" icon={<UserOutlined />} style={{ background: token.colorPrimary }} /> {user?.full_name}</Button>
            </Dropdown>
          </div>
        </Header>
        {impersonatedBy && (
          <div style={{ background: "#f59e0b", color: "#111827", padding: "8px 20px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", position: "sticky", top: 64, zIndex: 9 }}>
            <EyeOutlined />
            <span>Quản trị <b>{impersonatedBy.full_name}</b> đang xem dưới vai trò <b>{user?.role.name}</b> – tài khoản <b>{user?.username}</b>
              {user?.unit ? ` (${user.unit.name})` : ""}. Chế độ <b>chỉ xem</b>, không thực hiện thao tác thay người dùng.</span>
            <Button size="small" icon={<RollbackOutlined />} onClick={stopImpersonate} style={{ marginLeft: "auto" }}>Trở về quản trị</Button>
          </div>
        )}
        <Content style={{ padding: 20, maxWidth: 1600, width: "100%", margin: "0 auto" }}>
          <Routes>
            <Route path="/" element={<Workspace />} />
            <Route path="/dashboard" element={can("dashboard.view") ? <Dashboard /> : <Navigate to="/" replace />} />
            <Route path="/roles" element={can("role.manage") ? <RolesGuide /> : <Navigate to="/account" replace />} />
            <Route path="/account" element={<Account />} />
            <Route path="/plans/:id?" element={can("plan.view") ? <Plans /> : <Navigate to="/" replace />} />
            <Route path="/services" element={can("unit.manage", "am.view") ? <Services /> : <Navigate to="/" replace />} />
            <Route path="/units" element={can("unit.view") ? <Units /> : <Navigate to="/" replace />} />
            <Route path="/units/:id" element={can("unit.view") ? <UnitDetail /> : <Navigate to="/" replace />} />
            <Route path="/ranking" element={can("dashboard.view") ? <Ranking /> : <Navigate to="/" replace />} />
            <Route path="/alerts" element={can("alert.view") ? <Alerts /> : <Navigate to="/" replace />} />
            <Route path="/clusters" element={can("ml.run") ? <Clusters /> : <Navigate to="/" replace />} />
            <Route path="/planning" element={can("plan.view") ? <Planning /> : <Navigate to="/" replace />} />
            <Route path="/registers" element={can("task.receive", "task.issue", "task.sign") ? <Registers /> : <Navigate to="/" replace />} />
            <Route path="/assessment" element={can("assess.prepare", "assess.submit") ? <SelfAssessment /> : <Navigate to="/" replace />} />
            <Route path="/assessments" element={can("assess.review", "assess.publish") ? <Assessments /> : <Navigate to="/" replace />} />
            <Route path="/tasks" element={can("task.view") ? <Tasks /> : <Navigate to="/" replace />} />
            <Route path="/am" element={can("am.view") ? <AMPortfolio /> : <Navigate to="/" replace />} />
            <Route path="/data" element={can("data.view", "data.import") ? <DataPipeline /> : <Navigate to="/" replace />} />
            <Route path="/framework" element={can("criteria.manage") ? <Framework /> : <Navigate to="/" replace />} />
            <Route path="/reports" element={can("report.view") ? <Reports /> : <Navigate to="/" replace />} />
            <Route path="/admin/:section?" element={can("user.manage", "audit.view") ? <Admin /> : <Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  const { user, loading, mustChange } = useAuth();
  if (user && mustChange) return <ForceChangePassword />;
  if (loading) return <div style={{ display: "grid", placeItems: "center", height: "100vh" }}><Spin size="large" /></div>;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
      <Route path="/*" element={user ? <Shell /> : <Navigate to="/login" />} />
    </Routes>
  );
}
