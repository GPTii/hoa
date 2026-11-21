import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

/** Cấu hình công khai của bản triển khai (tên tỉnh, tên hệ thống...) – không cứng cho tỉnh nào */
export type SysConfig = {
  system_name: string;
  system_subtitle: string;
  province_name: string;
  province_label: string; // VD "Tỉnh Tây Ninh"
  org_name: string;
  demo_mode: boolean;
  password_min_length: number;
  password_require_complex: boolean;
};

const DEFAULT: SysConfig = {
  system_name: "DTI Platform", system_subtitle: "Trí tuệ dữ liệu chuyển đổi số", province_name: "", province_label: "",
  org_name: "", demo_mode: false, password_min_length: 6, password_require_complex: false,
};
const Ctx = createContext<{ cfg: SysConfig; reload: () => void }>({ cfg: DEFAULT, reload: () => {} });

export function SysConfigProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<SysConfig>(DEFAULT);
  const reload = () => api.get("/auth/public-config").then((r) => setCfg({ ...DEFAULT, ...r.data })).catch(() => {});
  useEffect(() => { reload(); }, []);
  useEffect(() => {
    document.title = cfg.province_label ? `${cfg.system_name} – ${cfg.province_label}` : cfg.system_name;
  }, [cfg]);
  return <Ctx.Provider value={{ cfg, reload }}>{children}</Ctx.Provider>;
}

export const useSysConfig = () => useContext(Ctx);
