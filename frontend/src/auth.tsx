import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

export type Me = {
  id: number;
  username: string;
  full_name: string;
  position?: string;
  role: { id: number; code: string; name: string; data_scope: string; level?: string };
  unit?: { id: number; name: string; unit_type: string } | null;
  region?: { id: number; name: string } | null;
};

type Imp = { id: number; username: string; full_name: string } | null;

type Ctx = {
  user: Me | null;
  perms: string[];
  loading: boolean;
  /** Quản trị viên đang "xem dưới vai trò" người dùng hiện tại (phiên chỉ xem) */
  impersonatedBy: Imp;
  /** Phải đổi mật khẩu (tài khoản mới, mật khẩu tạm, hết hạn) trước khi dùng hệ thống */
  mustChange: boolean;
  passwordChanged: () => void;
  can: (...p: string[]) => boolean;
  login: (u: string, p: string) => Promise<void>;
  impersonate: (userId: number) => Promise<void>;
  stopImpersonate: () => Promise<void>;
  logout: () => void;
};

const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [impersonatedBy, setImp] = useState<Imp>(null);
  const [mustChange, setMustChange] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("dti_token")) return setLoading(false);
    api.get("/auth/me").then((r) => { setUser(r.data.user); setPerms(r.data.permissions); setImp(r.data.impersonated_by); setMustChange(!!r.data.must_change_password); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const r = await api.post("/auth/login", { username, password });
    localStorage.setItem("dti_token", r.data.access_token);
    setUser(r.data.user);
    setPerms(r.data.permissions);
    setImp(null);
    setMustChange(!!r.data.must_change_password);
  };
  /** Chỉ quản trị hệ thống: chuyển sang xem giao diện, chức năng của tài khoản khác */
  const impersonate = async (userId: number) => {
    const r = await api.post(`/auth/impersonate/${userId}`);
    localStorage.setItem("dti_token", r.data.access_token);
    location.href = "/";
  };
  const stopImpersonate = async () => {
    const r = await api.post("/auth/stop-impersonate");
    localStorage.setItem("dti_token", r.data.access_token);
    location.href = "/roles";
  };
  const logout = async () => {
    try { await api.post("/auth/logout"); } catch { /* phiên có thể đã hết hạn */ }
    localStorage.removeItem("dti_token"); setUser(null); setPerms([]); setImp(null); location.href = "/login";
  };
  const can = (...p: string[]) => p.some((x) => perms.includes(x));
  return <AuthCtx.Provider value={{ user, perms, loading, impersonatedBy, mustChange, passwordChanged: () => setMustChange(false), can, login, impersonate, stopImpersonate, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
