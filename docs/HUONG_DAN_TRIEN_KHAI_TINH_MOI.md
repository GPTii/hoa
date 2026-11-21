# Hướng dẫn triển khai DTI Platform cho một tỉnh/thành mới

DTI Platform **dùng chung cho mọi tỉnh/thành** theo mô hình chính quyền địa phương 2 cấp (Tỉnh → Xã/Phường/Đặc khu).
Không có tên tỉnh nào bị "viết cứng" trong mã nguồn: tên tỉnh, tên hệ thống, đơn vị chủ quản, danh mục địa bàn – đơn vị,
tài khoản, bộ tiêu chí… đều là **dữ liệu cấu hình**.

**Tỉnh Tây Ninh** được giữ làm **bản mẫu** (dữ liệu mô phỏng 44 xã/phường, 247 đơn vị, 8 quý) để demo và đào tạo.

Mỗi tỉnh triển khai **một bản riêng** (máy chủ + CSDL riêng) – dữ liệu của tỉnh nằm trên hạ tầng của tỉnh.

---

## 0. Chuẩn bị (bộ phận kỹ thuật)

| Thành phần | Yêu cầu |
|---|---|
| Máy chủ | Windows/Linux, 4 vCPU, 8 GB RAM, 50 GB đĩa |
| Phần mềm | PostgreSQL ≥ 15, Python 3.12+, Node.js 20+ |
| Mạng | Truy cập được từ mạng truyền số liệu chuyên dùng / Internet có HTTPS |

```powershell
# 1. Cơ sở dữ liệu
createdb -U postgres dti_platform
# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
# 3. Cấu hình bí mật – tạo tệp backend/.env
#    DATABASE_URL=postgresql+psycopg://<user>:<mật khẩu>@<host>:5432/dti_platform
#    JWT_SECRET=<chuỗi ngẫu nhiên dài, không dùng mặc định>
# 4. Frontend
cd ..\frontend; npm install; npm run build
```

## 1. Khởi tạo hệ thống trống cho tỉnh

```powershell
cd backend
.\.venv\Scripts\python -m scripts.seed --blank --province "Bình Phước" --admin-password "MatKhauManh@2026"
# Thành phố trực thuộc TW:  --type "Thành phố" --province "Cần Thơ"
# Đơn vị chủ quản khác:     --org "Trung tâm Chuyển đổi số tỉnh Bình Phước"
```

Lệnh tạo **khung hệ thống**: 13 vai trò & ma trận quyền, bộ tiêu chí DTI (7 trụ cột / 24 tiêu chí), 16 nhóm giải pháp,
danh mục dịch vụ số, 4 kỳ đánh giá gần nhất, địa bàn cấp tỉnh và **1 tài khoản `admin`**. Chế độ demo **tắt**, chính sách
mật khẩu mạnh (≥ 8 ký tự, có chữ hoa/thường/số/ký tự đặc biệt) **bật**.

> ⚠ Lệnh xóa toàn bộ dữ liệu hiện có. Chỉ chạy khi cài mới.

Chạy máy chủ: `.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (frontend đã build được phục vụ cùng cổng).

## 2. Thiết lập trên giao diện – menu **Quản trị → Thiết lập tỉnh mới**

Đăng nhập `admin` (bắt buộc đổi mật khẩu lần đầu). Trang *Thiết lập tỉnh mới* hiển thị 7 bước, mỗi bước **tự kiểm tra
trạng thái** (Đã xong / Cần làm):

| Bước | Việc cần làm | Người thực hiện | Hệ thống kiểm tra |
|---|---|---|---|
| 1. Thông tin tỉnh | Tên tỉnh/thành, loại, tên hệ thống, đơn vị chủ quản (form ngay trên trang) | Quản trị | Đã đặt tên tỉnh |
| 2. Danh mục địa bàn & đơn vị | Tải **file mẫu danh mục** → điền sheet `dia_ban` (xã/phường/đặc khu theo nghị quyết sắp xếp) và `don_vi` (UBND tỉnh, VP, Sở, UBND xã, trường) → *Kiểm tra* → *Nhập* | Quản trị | Có xã/phường và UBND xã |
| 3. Kỳ đánh giá | Kiểm tra kỳ hiện hành; khóa số liệu kỳ đã công bố | Quản trị | Có kỳ hiện hành |
| 4. Bộ tiêu chí DTI | Điều chỉnh trọng số, mục tiêu cho phù hợp tỉnh (tổng trọng số trụ cột = 100) | Chuyên viên dữ liệu Sở KH&CN | Có tiêu chí, tổng trọng số = 100 |
| 5. Tài khoản cán bộ | Cấp tài khoản cấp tỉnh/Sở; **mỗi xã một "Quản trị hệ thống cấp xã"** (Nhập Excel); quản trị xã tự cấp cho cán bộ xã và trường | Quản trị → Quản trị xã | Có tài khoản cấp tỉnh/Sở và cấp xã |
| 6. Bảo mật | Tắt demo, rà chính sách mật khẩu, đổi mật khẩu admin, đặt `JWT_SECRET`, sao lưu lần đầu | Quản trị | Demo tắt và admin đã đổi mật khẩu |
| 7. Dữ liệu đầu tiên | Tải file khảo sát (Tích hợp dữ liệu) hoặc cấp khóa API cho trục LGSP | Chuyên viên dữ liệu | Đã có lô dữ liệu |

### File mẫu danh mục (bước 2)

**Sheet `dia_ban`**

| ma | ten | loai | dan_so | dien_tich_km2 |
|---|---|---|---|---|
| X001 | Phường Trung Tâm | phuong | 50000 | 20.5 |
| X002 | Xã Bình An | xa | 30000 | 85 |

**Sheet `don_vi`** – `phan_loai`: `ubnd_tinh`, `van_phong`, `so_nganh`, `ubnd_xa`, `thpt`, `thcs`, `tieu_hoc`, `mam_non`

| ma_don_vi | ten_don_vi | phan_loai | ma_dia_ban | ma_don_vi_cap_tren |
|---|---|---|---|---|
| HC.T01 | Ủy ban nhân dân tỉnh | ubnd_tinh | *(trống = cấp tỉnh)* | |
| HC.S09 | Sở Giáo dục và Đào tạo | so_nganh | | HC.T01 |
| HC.X001 | UBND Phường Trung Tâm | ubnd_xa | X001 | |
| GD.X001.TH1 | Trường Tiểu học Trung Tâm | tieu_hoc | X001 | HC.X001 |
| GD.X001.THPT1 | Trường THPT Trung Tâm | thpt | X001 | HC.S09 |

Quy tắc: UBND xã và trường MN/TH/THCS **bắt buộc** có `ma_dia_ban`; trường MN/TH/THCS có cấp trên là UBND xã (giao tiếp
nhiệm vụ 3 cấp), THPT có cấp trên là Sở GD&ĐT. Nhập lại cùng mã = cập nhật.

### File tài khoản (bước 5) – *Tài khoản người dùng → Nhập từ Excel*

| ten_dang_nhap | ho_ten | ma_vai_tro | ma_don_vi | chuc_vu |
|---|---|---|---|---|
| qt.trungtam | Nguyễn Văn A | quan_tri_xa | HC.X001 | Công chức VP – phụ trách CNTT |
| lanhdao.tinh | Trần Văn B | lanh_dao_tinh | HC.T01 | Phó Chủ tịch UBND tỉnh |

Hệ thống sinh mật khẩu tạm cho từng tài khoản (tải danh sách CSV để gửi), người dùng phải đổi ở lần đầu.

## 3. Vận hành định kỳ

- Đầu mỗi quý: *Kỳ đánh giá* → tạo kỳ kế tiếp → đặt làm hiện hành; khóa số liệu quý trước khi đã công bố.
- Hằng tuần: *Giám sát & sao lưu* → sao lưu, tải bản sao lưu lưu trữ ngoài máy chủ.
- Hằng tháng: *Tài khoản người dùng → Không hoạt động* → khóa tài khoản lâu không dùng; xem *Nhật ký & bảo mật*.
- Cán bộ nghỉ việc / chuyển công tác: *Tài khoản người dùng → Chuyển giao công việc*.

## 4. Bản mẫu Tây Ninh (demo, đào tạo)

```powershell
cd backend; .\.venv\Scripts\python -m scripts.seed     # mặc định = bản mẫu Tây Ninh
```

Tài khoản mẫu (mật khẩu `123456`): xem `README.md`.

## 5. Hướng phát triển: một nền tảng cho nhiều tỉnh (multi-tenant)

Mô hình hiện tại là *mỗi tỉnh một bản*. Để một máy chủ phục vụ nhiều tỉnh (VD nền tảng cấp quốc gia so sánh DTI giữa các
tỉnh), cần thêm mã tỉnh (`tenant_id`) vào các bảng nghiệp vụ, lọc theo tỉnh ở mọi truy vấn và phân quyền quản trị theo tỉnh.
