import { useEffect, useState } from "react";
import { Alert, Button, Card, Select, Space, Table, Tabs, Tag } from "antd";
import { FileExcelOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/common";
import { TaskDetail } from "./Tasks";

const fmt = (d?: string, t = false) => (d ? dayjs(d).format(t ? "HH:mm DD/MM/YYYY" : "DD/MM/YYYY") : "");

/** Sổ đăng ký văn bản đến / văn bản đi của đơn vị (theo Nghị định 30/2020/NĐ-CP về công tác văn thư) */
export default function Registers() {
  const { user } = useAuth();
  const [kind, setKind] = useState<"den" | "di">("den");
  const [year, setYear] = useState(dayjs().year());
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<number | null>(null);
  const load = () => {
    setLoading(true);
    api.get(`/tasks/registers/${kind}`, { params: { year } }).then((r) => setRows(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, [kind, year]);
  const exportX = async () => {
    const r = await api.get(`/tasks/registers/${kind}/export`, { params: { year }, responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(r.data);
    a.download = `so_van_ban_${kind === "den" ? "den" : "di"}_${year}.xlsx`;
    a.click();
  };
  const den = [
    { title: "Số đến", dataIndex: "so_den", width: 70, fixed: "left" as const },
    { title: "Ngày đến", dataIndex: "ngay_den", width: 140, render: (v: string) => fmt(v, true) },
    { title: "Nơi gửi", dataIndex: "noi_gui", width: 200 },
    { title: "Số, ký hiệu", dataIndex: "so_ky_hieu", width: 140 },
    { title: "Ngày văn bản", dataIndex: "ngay_van_ban", width: 110, render: (v: string) => fmt(v) },
    { title: "Trích yếu", dataIndex: "trich_yeu", width: 320, render: (v: string, r: any) => <a onClick={() => setDetail(r.task_id)}>{v}</a> },
    { title: "Độ khẩn", dataIndex: "do_khan", width: 80, render: (v: string) => v === "Khẩn" ? <Tag color="red">Khẩn</Tag> : v },
    { title: "Ý kiến chỉ đạo", dataIndex: "y_kien_chi_dao", width: 220 },
    { title: "Đơn vị / người xử lý", dataIndex: "don_vi_xu_ly", width: 200 },
    { title: "Hạn xử lý", dataIndex: "han_xu_ly", width: 100, render: (v: string) => fmt(v) },
    { title: "Tình trạng", dataIndex: "trang_thai", width: 170 },
  ];
  const di = [
    { title: "Số đi", dataIndex: "so_di", width: 70, fixed: "left" as const },
    { title: "Ngày ban hành", dataIndex: "ngay_ban_hanh", width: 140, render: (v: string) => fmt(v, true) },
    { title: "Số, ký hiệu", dataIndex: "so_ky_hieu", width: 130, render: (v: string) => <b>{v}</b> },
    { title: "Trích yếu", dataIndex: "trich_yeu", width: 340, render: (v: string, r: any) => <a onClick={() => setDetail(r.task_id)}>{v}</a> },
    { title: "Người ký", dataIndex: "nguoi_ky", width: 200 },
    { title: "Nơi nhận", dataIndex: "noi_nhan", width: 200 },
    { title: "Trả lời văn bản", dataIndex: "tra_loi_van_ban", width: 140 },
    { title: "Người phát hành", dataIndex: "nguoi_phat_hanh", width: 150 },
    { title: "Tình trạng", dataIndex: "trang_thai", width: 160 },
  ];
  return (
    <>
      <PageHeader title="Sổ văn bản" sub={`${user?.unit?.name ?? ""} – đăng ký văn bản đến, văn bản đi theo Nghị định 30/2020/NĐ-CP`} />
      <Card size="small">
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message={kind === "den"
            ? "Văn bản đến được văn thư tiếp nhận, cấp số đến (liên tiếp theo năm) và trình lãnh đạo cho ý kiến chỉ đạo, phân công xử lý."
            : "Văn bản đi (báo cáo trả lời) chỉ được cấp số sau khi người có thẩm quyền ký; văn thư cấp số, ngày ban hành, đăng ký sổ và phát hành."} />
        <Tabs activeKey={kind} onChange={(k) => setKind(k as any)}
          tabBarExtraContent={<Space>
            <Select value={year} onChange={setYear} style={{ width: 100 }}
              options={[0, 1, 2].map((i) => ({ value: dayjs().year() - i, label: `Năm ${dayjs().year() - i}` }))} />
            <Button icon={<FileExcelOutlined />} onClick={exportX}>Xuất sổ</Button>
          </Space>}
          items={[{ key: "den", label: "Sổ văn bản đến" }, { key: "di", label: "Sổ văn bản đi" }]} />
        <Table size="small" rowKey={(r: any) => `${kind}-${r.so_den ?? r.so_di}-${r.task_id}`} loading={loading} dataSource={rows}
          columns={kind === "den" ? den : di} scroll={{ x: 1600 }} pagination={{ pageSize: 15 }}
          locale={{ emptyText: "Chưa có văn bản trong sổ" }} />
      </Card>
      {detail && <TaskDetail id={detail} onClose={() => setDetail(null)} onChanged={load} />}
    </>
  );
}
