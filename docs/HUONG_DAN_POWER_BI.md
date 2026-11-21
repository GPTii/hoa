# Kết nối Power BI với DTI Platform

Đề cương mục 4.4: *"Power BI có thể được sử dụng để hỗ trợ phân tích và báo cáo"*. Hệ thống cung cấp sẵn tầng dữ liệu phẳng
cho công cụ BI trong schema `gold` (tạo tự động khi khởi động backend / chạy seed):

| View | Nội dung | Dùng cho |
|---|---|---|
| `gold.v_bi_dti` | DTI từng đơn vị × kỳ, mức độ, hạng, tăng/giảm, địa bàn, loại hình | Bảng xếp hạng, xu hướng, bản đồ theo xã |
| `gold.v_bi_tru_cot` | Điểm 7 trụ cột × đơn vị × kỳ | Radar, ma trận nhiệt trụ cột |
| `gold.v_bi_tieu_chi` | Giá trị & điểm 24 tiêu chí | Phân tích sâu tiêu chí yếu |
| `gold.v_bi_dia_ban` | Điểm trung bình xã/phường × kỳ | So sánh khu vực |
| `gold.v_bi_canh_bao` | Cảnh báo theo kỳ | Theo dõi đơn vị cần quan tâm |
| `gold.v_bi_nhiem_vu` | Tiến độ nhiệm vụ, quá hạn | Giám sát điều hành |

## 1. Tạo tài khoản CSDL chỉ đọc (khuyến nghị)

```sql
CREATE ROLE bi_reader LOGIN PASSWORD 'DoiMatKhauNay@2026';
GRANT USAGE ON SCHEMA gold TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO bi_reader;   -- gồm cả các view v_bi_*
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO bi_reader;
```

> Các view `v_bi_*` đọc từ bảng trong schema `public`; PostgreSQL kiểm tra quyền theo chủ sở hữu view nên `bi_reader`
> chỉ cần quyền trên schema `gold`.

## 2. Kết nối từ Power BI Desktop

1. *Get Data → PostgreSQL database*.
2. Server: `<máy chủ>:5433` (bản phát triển) · Database: `dti_platform`.
3. Chế độ: **Import** (dữ liệu cập nhật theo quý) hoặc DirectQuery.
4. Đăng nhập bằng `bi_reader`, chọn các view `gold.v_bi_*`.
5. Tạo quan hệ: `v_bi_dti[ma_don_vi]` ↔ `v_bi_tru_cot[ma_don_vi]`, cùng cột `ky`.

## 3. Gợi ý báo cáo

- **Trang tổng quan:** thẻ DTI trung bình theo `ky`, biểu đồ đường `nam/quy` × `diem_dti`, cột chồng `muc_do`.
- **Trang địa bàn:** bảng `v_bi_dia_ban` có định dạng màu theo `dti_tb`; lọc theo `ky`.
- **Trang trụ cột:** ma trận `dia_ban` × `tru_cot` giá trị `diem` trung bình.
- **Trang điều hành:** `v_bi_nhiem_vu` – tỷ lệ `qua_han` theo `co_quan_giao`, `don_vi_thuc_hien`.

Lưu ý: Power BI đọc trực tiếp CSDL nên **không áp dụng phân quyền theo vai trò** của ứng dụng – chỉ cấp cho bộ phận phân
tích cấp tỉnh. Người dùng nghiệp vụ dùng dashboard và báo cáo Excel trong ứng dụng (đã lọc theo phạm vi).
