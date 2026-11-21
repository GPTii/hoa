import { useEffect, useState } from "react";
import { Badge, Button, Empty, List, Popover, Space, Tag, Typography } from "antd";
import { BellOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import { api } from "../api";

const KIND: Record<string, [string, string]> = {
  van_ban_den: ["blue", "Văn bản đến"], phan_cong: ["purple", "Phân công"], trinh: ["orange", "Chờ duyệt"],
  bao_cao: ["green", "Báo cáo"], ket_qua: ["cyan", "Kết quả"], don_doc: ["red", "Đôn đốc"], he_thong: ["default", "Hệ thống"],
};

export default function NotificationBell() {
  const nav = useNavigate();
  const [data, setData] = useState<any>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const load = () => api.get("/notifications").then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  const go = async (n: any) => {
    if (!n.is_read) await api.post(`/notifications/${n.id}/read`);
    setOpen(false); load();
    if (n.task_id) nav(`/tasks?open=${n.task_id}`);
  };
  const content = (
    <div style={{ width: 380 }}>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 6 }}>
        <b>Thông báo</b>
        {data.unread > 0 && <Button size="small" type="link" onClick={() => api.post("/notifications/read-all").then(load)}>Đánh dấu đã đọc hết</Button>}
      </Space>
      {data.items.length ? <List size="small" style={{ maxHeight: 420, overflow: "auto" }} dataSource={data.items} renderItem={(n: any) => (
        <List.Item onClick={() => go(n)} style={{ cursor: "pointer", background: n.is_read ? undefined : "#eff6ff", paddingInline: 8 }}>
          <div>
            <Space size={4}><Tag color={KIND[n.kind]?.[0]}>{KIND[n.kind]?.[1] ?? n.kind}</Tag>
              <span className="muted" style={{ fontSize: 11 }}>{dayjs(n.created_at).format("HH:mm DD/MM")}</span></Space>
            <div style={{ fontSize: 13, fontWeight: n.is_read ? 400 : 600 }}>{n.title}</div>
            {n.body && <Typography.Text type="secondary" style={{ fontSize: 12 }}>{n.body}</Typography.Text>}
          </div>
        </List.Item>)} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có thông báo" />}
    </div>
  );
  return (
    <Popover content={content} trigger="click" open={open} onOpenChange={(o) => { setOpen(o); if (o) load(); }} placement="bottomRight">
      <Button type="text" aria-label="Thông báo" style={{ paddingInline: 8 }}>
        <Badge count={data.unread} size="small"><BellOutlined style={{ fontSize: 18 }} /></Badge>
      </Button>
    </Popover>
  );
}
