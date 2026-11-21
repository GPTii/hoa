import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App as AntApp, ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import dayjs from "dayjs";
import "dayjs/locale/vi";
import { AuthProvider } from "./auth";
import { SysConfigProvider } from "./sysconfig";
import App from "./App";
import "./styles.css";

dayjs.locale("vi");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={viVN} theme={{
      token: { colorPrimary: "#1d4ed8", borderRadius: 8, fontFamily: "'Be Vietnam Pro', 'Segoe UI', Roboto, sans-serif", colorBgLayout: "#f4f6fa" },
      components: { Layout: { siderBg: "#0b1f44", headerBg: "#ffffff" }, Menu: { darkItemBg: "#0b1f44", darkSubMenuItemBg: "#08183a" } },
    }}>
      <AntApp>
        <BrowserRouter>
          <SysConfigProvider><AuthProvider><App /></AuthProvider></SysConfigProvider>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
