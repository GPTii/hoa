# Kết quả thực nghiệm

*Sinh tự động ngày 19/11/2026 bằng `python -m scripts.report_experiment` – bộ dữ liệu: Tỉnh Tây Ninh (dữ liệu mô phỏng).*

## 1. Quy mô bộ dữ liệu thực nghiệm

| Hạng mục | Số lượng | Ghi chú |
|---|---|---|
| Đơn vị | 247 | 58 cơ quan hành chính, 189 cơ sở giáo dục |
| Kỳ đánh giá | 8 | 2025-Q1 → 2026-Q4 |
| Tiêu chí / trụ cột | 24 | 7 trụ cột |
| Nhiệm vụ / lượt giao | 85 | 5100 lượt giao |
| Người dùng | 15 |  |
| Bản ghi schema bronze | 4852 |  |
| Bản ghi schema gold | 82937 |  |
| Bản ghi schema public | 8593 |  |
| Bản ghi schema silver | 40210 |  |

## 2. Pipeline Bronze → Silver → Gold

| Nguồn | Số lô | Dòng thô (Bronze) | Giá trị hợp lệ (Silver) | Giá trị bị loại |
|---|---|---|---|---|
| upload_csv | 8 | 1984 | 37326 | 32 |
| system_sync | 8 | 2852 | 2852 | 0 |

Các lỗi được phát hiện và loại ở bước làm sạch:

| Lý do loại (Silver) | Số lượng |
|---|---|
| Không chuyển được 'chưa rõ' sang số | 9 |
| Mã đơn vị không tồn tại trong danh mục | 8 |
| Tỷ lệ -5.0 nằm ngoài miền [0, 100] | 7 |
| Không chuyển được 'abc' sang số | 7 |
| Tỷ lệ 120.0 nằm ngoài miền [0, 100] | 1 |

Thời gian tính toàn bộ tầng Gold cho 1 kỳ (247 đơn vị): **0.39 giây**.


## 3. Kết quả Digital Transformation Score

### 3.1 Diễn biến theo kỳ

| Kỳ | Số đơn vị | DTI TB | Thấp nhất | Cao nhất | Độ lệch chuẩn |
|---|---|---|---|---|---|
| 2025-Q1 | 247 | 45.14 | 6.41 | 89.99 | 17.47 |
| 2025-Q2 | 247 | 47.78 | 11.87 | 88.36 | 17.33 |
| 2025-Q3 | 247 | 49.89 | 8.43 | 90.64 | 17.64 |
| 2025-Q4 | 247 | 52.08 | 10.87 | 88.85 | 17.51 |
| 2026-Q1 | 247 | 53.04 | 9.93 | 92.45 | 17.80 |
| 2026-Q2 | 247 | 54.92 | 15.20 | 94.07 | 17.25 |
| 2026-Q3 | 247 | 56.52 | 13.50 | 92.46 | 16.88 |
| 2026-Q4 | 247 | 58.19 | 12.92 | 95.91 | 16.75 |

### 3.2 Phân loại mức độ – Quý 4/2026

| Mức độ | Số đơn vị | Tỷ lệ (%) |
|---|---|---|
| Nâng cao | 53 | 21.50 |
| Cơ bản | 62 | 25.10 |
| Phát triển | 105 | 42.50 |
| Dẫn đầu | 13 | 5.30 |
| Khởi đầu | 14 | 5.70 |

### 3.3 Theo loại hình đơn vị

| Loại hình | Số đơn vị | DTI TB |
|---|---|---|
| van_phong | 1 | 75.35 |
| so_nganh | 12 | 75.01 |
| ubnd_tinh | 1 | 70.49 |
| thpt | 25 | 70.20 |
| thcs | 44 | 60.64 |
| ubnd_xa | 44 | 57.38 |
| tieu_hoc | 76 | 56.34 |
| mam_non | 44 | 47.69 |

### 3.4 Theo trụ cột (trụ cột yếu nhất là ưu tiên hoạch định)

| Trụ cột | Trọng số | Điểm TB |
|---|---|---|
| Nhận thức số | 10.00 | 73.90 |
| Thể chế số | 10.00 | 52.37 |
| Hạ tầng số | 15.00 | 62.37 |
| Nhân lực số | 15.00 | 57.42 |
| An toàn thông tin | 15.00 | 42.22 |
| Hoạt động điều hành số | 20.00 | 63.95 |
| Dịch vụ số & CĐS chuyên ngành | 15.00 | 56.50 |

## 4. Cảnh báo, đơn vị ưu tiên, đề xuất giải pháp

| Loại cảnh báo | Mức | Số lượng |
|---|---|---|
| SCORE_DROP | trung_binh | 31 |
| SCORE_DROP | cao | 32 |
| OVERDUE_TASK | trung_binh | 85 |
| WEAK_PILLAR | trung_binh | 315 |
| LOW_SCORE | trung_binh | 22 |
| LOW_SCORE | cao | 14 |
| EXPIRING_SERVICE | thap | 481 |

**5 đơn vị cần ưu tiên nhất:**

| Đơn vị ưu tiên | Chỉ số ưu tiên | Lý do |
|---|---|---|
| Trường Mầm non Đức Hòa | 79.54 | DTI thấp 12.9, giảm 15.1 điểm, 6 trụ cột yếu, 1 nhiệm vụ trễ hạn |
| UBND Xã Mỹ Yên | 67.37 | DTI thấp 20.4, giảm 9.3 điểm, 6 trụ cột yếu, 1 nhiệm vụ trễ hạn |
| Trường Mầm non Tân Biên | 66.38 | DTI thấp 26.1, giảm 24.9 điểm, 5 trụ cột yếu |
| Trường THCS Thạnh Hóa | 66.26 | DTI thấp 28.6, giảm 17.9 điểm, 4 trụ cột yếu, 1 nhiệm vụ trễ hạn |
| Trường Mầm non Bến Cầu | 65.67 | DTI thấp 18.1, 6 trụ cột yếu, 1 nhiệm vụ trễ hạn |

**Nhóm giải pháp được đề xuất nhiều nhất:**

| Nhóm giải pháp | Số đơn vị | Điểm ưu tiên TB |
|---|---|---|
| Họp trực tuyến, phòng họp không giấy | 184 | 60.23 |
| Thanh toán không dùng tiền mặt | 183 | 57.59 |
| Xây dựng lớp học số | 166 | 60.77 |
| Bồi dưỡng kỹ năng số & chữ ký số | 158 | 51.62 |
| Bảo đảm an toàn thông tin theo cấp độ | 155 | 72.60 |
| Sao lưu & phục hồi dữ liệu | 127 | 90.00 |
| Nâng cao hiệu quả khai thác dịch vụ số | 122 | 42.33 |
| Điều hành không giấy trên hệ thống VBĐH | 115 | 55.15 |

## 5. Machine Learning

### 5.1 Phân cụm K-Means

| k | Silhouette | Inertia |
|---|---|---|
| 2.00 | 0.29 | 1117.10 |
| 3.00 | 0.22 | 950.40 |
| 4.00 | 0.21 | 853.30 |
| 5.00 | 0.22 | 771.40 |
| 6.00 | 0.21 | 713.20 |

Silhouette cao nhất tại k = 2. Hệ thống chọn **k = 4** vì cho 4 nhóm có ý nghĩa quản lý (dẫn đầu / khá / trung bình / yếu) trong khi silhouette chênh lệch không đáng kể – đây là đánh đổi giữa độ tách cụm và tính diễn giải.

| Cụm (k=4) | Số đơn vị | DTI TB |
|---|---|---|
| Nhóm dẫn đầu | 83 | 76.33 |
| Nhóm phát triển khá | 74 | 58.20 |
| Nhóm trung bình – cần hỗ trợ | 46 | 43.10 |
| Nhóm yếu – ưu tiên cao | 44 | 39.75 |

### 5.2 Dự báo DTI kỳ kế tiếp – backtest (247 đơn vị)

| Mô hình | MAE | RMSE | MAPE (%) |
|---|---|---|---|
| Hồi quy tuyến tính (hệ thống) | 7.57 | 9.45 | 14.93 |
| Cơ sở: giữ nguyên kỳ trước | 8.42 | 10.35 | 16.41 |

Mô hình giảm sai số tuyệt đối trung bình **10.2%** so với mô hình cơ sở.


## 6. Kiểm thử chức năng

Các bộ kiểm thử tự động (chạy khi backend hoạt động ở cổng 8000):

| Bộ kiểm thử | Phạm vi |
|---|---|
| scripts.smoke_test | Toàn bộ API theo vai trò; phạm vi dữ liệu; luồng nhiệm vụ 2 & 3 cấp; pipeline nhập file lỗi; quản trị phân cấp; bàn làm việc |
| scripts.test_privacy_features | Che thông tin hệ thống; thông báo; số đến; đôn đốc; đính kèm; tự khai báo hạ tầng |
| scripts.test_impersonation | Quản trị xem dưới vai trò (chỉ xem), trở về, nhật ký |
| scripts.test_admin_ops | 8 nhóm quản trị: khóa đăng nhập, phiên, đổi MK bắt buộc, nhập/xuất, chuyển giao, cấu hình, kỳ, thông báo, giám sát, sao lưu, nhật ký, khóa API |
| scripts.test_outline_features | Danh mục dịch vụ; cơ quan cấp tỉnh; kế hoạch chăm sóc AM; lập kế hoạch cải thiện; báo cáo bổ sung; đánh giá ML; view Power BI |
| scripts.test_new_province | Khởi tạo tỉnh mới, nhập danh mục Excel, trạng thái thiết lập (chạy trên hệ thống --blank) |

Kết quả lần chạy gần nhất: **tất cả đạt** (xem log khi chạy lại).
