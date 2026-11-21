import axios from "axios";
import { message } from "antd";

export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("dti_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    const onLogin = location.pathname.startsWith("/login");
    if (status === 401 && !onLogin) {
      // phiên hết hạn / bị thu hồi (quản trị buộc đăng xuất, đổi mật khẩu ở thiết bị khác...)
      localStorage.removeItem("dti_token");
      sessionStorage.setItem("dti_logout_reason", typeof detail === "string" ? detail : "Phiên đăng nhập đã kết thúc");
      location.href = "/login";
    } else {
      message.error(typeof detail === "string" ? detail : "Có lỗi xảy ra, vui lòng thử lại");
    }
    return Promise.reject(err);
  },
);

export async function download(url: string, params: Record<string, unknown>, filename: string) {
  const r = await api.get(url, { params, responseType: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(r.data);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
