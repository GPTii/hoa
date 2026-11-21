import { useState } from "react";
import { Button, Card, Col, List, Row, Select, Space, Typography } from "antd";
import { FileExcelOutlined } from "@ant-design/icons";
import { download } from "../api";
import { useAuth } from "../auth";
import { PageHeader, PeriodSelect, UNIT_TYPE, useRegions } from "../components/common";

export default function Reports() {
  const { can, user } = useAuth();
  const regions = useRegions();
  const [period, setPeriod] = useState<string>();
  const [unitType, setUnitType] = useState<string>();
  const [regionId, setRegionId] = useState<number>();
  const [busy, setBusy] = useState(false);
  const exp = async () => {
    setBusy(true);
    try { await download("/reports/dti.xlsx", { period, unit_type: unitType, region_id: regionId }, `bao_cao_DTI_${period}.xlsx`); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader title="Báo cáo & thống kê" sub="Báo cáo tổng hợp theo phạm vi dữ liệu được phân quyền" />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Báo cáo kết quả đánh giá chuyển đổi số (Excel)">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Space wrap>
                <PeriodSelect value={period} onChange={setPeriod} />
                <Select allowClear placeholder="Loại hình" style={{ width: 180 }} value={unitType} onChange={setUnitType} options={Object.entries(UNIT_TYPE).map(([value, label]) => ({ value, label }))} />
                {user?.role.data_scope === "all" && <Select allowClear showSearch optionFilterProp="label" placeholder="Địa bàn" style={{ width: 200 }} value={regionId} onChange={setRegionId}
                  options={regions.map((r) => ({ value: r.id, label: r.name }))} />}
              </Space>
              <List size="small" bordered dataSource={["Tổng quan kỳ đánh giá", "Xếp hạng đơn vị + điểm 7 trụ cột", "Tổng hợp theo xã/phường", "Danh sách cảnh báo", "Đề xuất nhóm giải pháp theo đơn vị"]}
                renderItem={(i, idx) => <List.Item>Sheet {idx + 1}: {i}</List.Item>} />
              <Button type="primary" icon={<FileExcelOutlined />} loading={busy} disabled={!can("report.export")} onClick={exp}>Xuất báo cáo Excel</Button>
              {!can("report.export") && <Typography.Text type="secondary">Vai trò của bạn chỉ được xem báo cáo trên hệ thống, không xuất tệp.</Typography.Text>}
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Báo cáo khác (Excel)" style={{ marginBottom: 16 }}>
            <List size="small" dataSource={[
              ["Diễn biến DTI theo thời gian", "Đơn vị × kỳ, địa bàn × kỳ, tăng/giảm cả giai đoạn", () => download("/reports/trend.xlsx", { unit_type: unitType }, "bao_cao_dien_bien_DTI.xlsx"), can("report.export")],
              ["Tiến độ thực hiện nhiệm vụ", "Tỷ lệ hoàn thành, quá hạn, hoàn thành trễ theo đơn vị", () => download("/reports/tasks.xlsx", {}, "bao_cao_nhiem_vu.xlsx"), can("report.export") && can("task.view")],
            ] as any[]} renderItem={([t, d, fn, ok]: any) => <List.Item actions={[<Button key="x" size="small" icon={<FileExcelOutlined />} disabled={!ok} onClick={fn}>Xuất</Button>]}>
              <List.Item.Meta title={t} description={d} /></List.Item>} />
          </Card>
          <Card title="Báo cáo trực tuyến">
            <List dataSource={[
              ["Tổng quan chuyển đổi số", "/dashboard", "KPI, xu hướng, phân loại, top/bottom"],
              ["Xếp hạng & so sánh", "/ranking", "Theo đơn vị, xã/phường, so sánh nhiều đơn vị"],
              ["Cảnh báo & ưu tiên", "/alerts", "Đơn vị cần quan tâm, lý do"],
              ["Hỗ trợ hoạch định", "/planning", "Nhóm giải pháp, đơn vị cần triển khai"],
              ["Theo dõi nhiệm vụ", "/tasks", "Tiến độ, quá hạn theo đơn vị"],
            ]} renderItem={([t, href, d]) => <List.Item><List.Item.Meta title={<a href={href}>{t}</a>} description={d} /></List.Item>} />
          </Card>
        </Col>
      </Row>
    </>
  );
}
