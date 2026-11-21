# DTI Platform – Nền tảng Trí tuệ Dữ liệu hỗ trợ quản trị chuyển đổi số

Đồ án tốt nghiệp: *Xây dựng nền tảng trí tuệ dữ liệu hỗ trợ quản trị chuyển đổi số cho cơ quan hành chính và cơ sở giáo dục*.

Nền tảng **dùng chung cho mọi tỉnh/thành** theo mô hình chính quyền địa phương 2 cấp (Tỉnh → Xã/Phường/Đặc khu) – tên tỉnh,
danh mục địa bàn, đơn vị, tài khoản đều là cấu hình. **Tỉnh Tây Ninh là bản mẫu thí điểm** (dữ liệu mô phỏng).

```powershell
cd backend; .\.venv\Scripts\python -m scripts.seed                                    # bản mẫu Tây Ninh (demo)
cd backend; .\.venv\Scripts\python -m scripts.seed --blank --province "Bình Phước"    # hệ thống trống cho tỉnh mới
```

Triển khai cho tỉnh mới: đăng nhập `admin` → **Quản trị → Thiết lập tỉnh mới** (7 bước, tự kiểm tra trạng thái) –
chi tiết trong [docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md](docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md).

| Thành phần | Công nghệ |
|---|---|
| Frontend | React 18 + TypeScript + Vite, Ant Design 5, Recharts |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2, Pydantic 2 |
| CSDL | **PostgreSQL 17** – schema `public` (nghiệp vụ), `bronze`, `silver`, `gold` (Medallion) |
| Xử lý dữ liệu | Pandas (Bronze → Silver → Gold) |
| ML | scikit-learn: K-Means phân cụm, hồi quy tuyến tính dự báo |
| Bảo mật | JWT + RBAC (32 quyền, 14 vai trò) + phạm vi dữ liệu theo dòng (toàn tỉnh / xã / đơn vị / AM) |

## 🚀 Chạy trên máy mới – chỉ cần 1 file

> **Clone về → bấm đúp `start.bat` → đợi → trình duyệt tự mở http://localhost:8000.**
> Không cần cài trước Python, Node.js hay PostgreSQL. Không cần chạy file nào khác.

### Các bước

**Cách A – có Git:**

```powershell
git clone https://github.com/GPTii/hoa.git
```

**Cách B – không có Git:** trên trang https://github.com/GPTii/hoa bấm nút xanh **Code → Download ZIP**, rồi giải nén
(chuột phải → *Extract All*). Nên để ở đường dẫn ngắn, không dấu, ví dụ `D:\hoa`.

1. Mở thư mục vừa tải về (`hoa`, hoặc `hoa-main` nếu tải ZIP), **bấm đúp `start.bat`**.
   Nếu Windows hiện cảnh báo *“Windows protected your PC”* → bấm **More info → Run anyway**.
2. **Lần đầu** (5–15 phút, cần Internet) cửa sổ sẽ tự làm lần lượt:

   | Bước | Việc tự động | Ghi chú |
   |---|---|---|
   | 1 | Kiểm tra **Python 3.11–3.13** | Thiếu thì cài Python 3.12 cho tài khoản hiện tại |
   | 2 | Kiểm tra **Node.js ≥ 18** | Thiếu thì tải bản portable vào `.tools\node` |
   | 3 | Kiểm tra **PostgreSQL ≥ 15** | Thiếu thì tải bản portable vào `.tools\pgsql` (không tạo service, không đụng PostgreSQL có sẵn) |
   | 4 | Tạo CSDL riêng của dự án (thư mục `.pgdata`, cổng **5433**) | |
   | 5 | **Nạp dữ liệu từ `database\dti_platform.sql`** + tệp đính kèm `database\uploads` | Dữ liệu giống hệt máy đã xuất |
   | 6 | Tạo môi trường Python `backend\.venv`, cài thư viện | |
   | 7 | Cài thư viện giao diện, build `frontend\dist` | |

3. Khi thấy dòng **`DTI Platform đang chạy: http://localhost:8000`** là xong – trình duyệt tự mở.
   Đăng nhập `admin` / `123456` hoặc chọn tài khoản thử nghiệm ngay ở trang đăng nhập.
4. **Các lần sau** bấm `start.bat` chỉ mất vài giây. **Đóng cửa sổ đen = tắt ứng dụng.**

### Các file trong thư mục gốc dùng để làm gì?

| File | Ai dùng | Khi nào |
|---|---|---|
| **`start.bat`** | Mọi người | **Mỗi lần muốn chạy ứng dụng** (lần đầu tự cài đặt) – *đây là file duy nhất cần bấm* |
| `setup.bat` | Khi gặp sự cố | Cài lại môi trường. `setup.bat -ResetData` = xóa dữ liệu trên máy, nạp lại từ file SQL |
| `export-db.bat` | Người đang phát triển | **Trước khi push** – xuất dữ liệu hiện tại ra `database\` để máy khác clone về có dữ liệu y hệt |
| `database\dti_platform.sql` | *(không bấm)* | File dữ liệu – `start.bat` tự nạp ở lần đầu |
| `start-dev.ps1` | Người đang phát triển | Chạy chế độ phát triển (giao diện tự cập nhật khi sửa code) |

### Cập nhật dữ liệu cho các máy khác

```text
Máy đang làm:   export-db.bat  →  git add database  →  git commit  →  git push
Máy khác:       git pull       →  setup.bat -ResetData   (nạp lại dữ liệu mới)  →  start.bat
```

> Máy đã có dữ liệu thì `start.bat` **giữ nguyên** dữ liệu trên máy (không ghi đè). Muốn lấy dữ liệu mới từ git phải chạy `setup.bat -ResetData`.

### Yêu cầu & xử lý sự cố

- Windows 10/11 64-bit; cần Internet ở lần chạy đầu; khoảng 1,5 GB ổ đĩa trống.
- Cổng **5433** (CSDL) và **8000** (ứng dụng) phải trống.

| Hiện tượng | Cách xử lý |
|---|---|
| Báo “Cổng 8000 đang có chương trình khác” | Ứng dụng đang chạy ở cửa sổ khác → mở http://localhost:8000, hoặc đóng cửa sổ cũ rồi chạy lại |
| Báo “Cổng 5433 đang bị chương trình khác dùng” | Tắt chương trình đang dùng cổng 5433 rồi chạy lại |
| Cài thư viện thất bại | Kiểm tra mạng rồi chạy `setup.bat` |
| Muốn làm lại từ đầu | Xóa các thư mục `.pgdata`, `.tools`, `backend\.venv`, `frontend\node_modules` rồi bấm `start.bat` |
| Xem lỗi máy chủ | File `.api.log` và `.api.log.err` trong thư mục gốc |

## Chạy chế độ phát triển

```powershell
.\start-dev.ps1 -Seed     # tạo lại CSDL + dữ liệu mô phỏng, rồi chạy backend + frontend (hot reload)
.\start-dev.ps1           # các lần sau
```

- Giao diện dev: http://localhost:5173 · API docs (Swagger): http://localhost:8000/docs
- PostgreSQL của dự án: `localhost:5433`, DB `dti_platform`, user `dti` / `dtipass` (cluster riêng trong `.pgdata`, không đụng tới PostgreSQL cài sẵn ở cổng 5432)
- Kiểm thử API: `cd backend; .\.venv\Scripts\python -m scripts.smoke_test`

## Tài khoản thử nghiệm (mật khẩu `123456`)

Vai trò = **Cấp × Chức danh**. Mỗi người chỉ thấy menu và dữ liệu thuộc phần việc của mình.
Ở trang đăng nhập có sẵn danh sách tài khoản – bấm vào một dòng để điền nhanh.

| Cấp | Tài khoản | Vai trò | Phạm vi dữ liệu | Việc chính trong hệ thống |
|---|---|---|---|---|
| Tỉnh | `lanhdao.tinh` | Lãnh đạo UBND tỉnh | Toàn tỉnh | Giao nhiệm vụ, xác nhận báo cáo, **công bố kết quả đánh giá CĐS** |
| Tỉnh | `vp.ubndtinh` | Chuyên viên VP UBND tỉnh | Toàn tỉnh | Theo dõi, đôn đốc, xác nhận / trả lại báo cáo |
| Sở | `skhcn` | Chuyên viên dữ liệu Sở KH&CN | Toàn tỉnh | Nhập dữ liệu, bộ tiêu chí, ML, **thẩm định phiếu tự đánh giá** của cơ quan hành chính |
| Sở | `sgddt` | Lãnh đạo Sở GD&ĐT | Toàn ngành giáo dục | Giao việc cho trường, xác nhận, **thẩm định phiếu** của trường học |
| Sở | `lanhdao.stp` | Giám đốc Sở Tư pháp | Cơ quan mình | Tiếp nhận – phân công – ký – phát hành báo cáo; tự đánh giá CĐS của Sở |
| Xã | `khanhhau` | Chủ tịch UBND phường Khánh Hậu | Địa bàn phường | Bút phê, phân công, giao tiếp xuống trường, **ký duyệt**, duyệt & nộp phiếu tự đánh giá |
| Xã | `vanthu.khanhhau` | Văn thư UBND phường | Đơn vị mình | Tiếp nhận văn bản đến (sổ đến), **cấp số & phát hành** văn bản đi (sổ đi) |
| Xã | `tp.khanhhau` | Trưởng phòng VH-XH | Địa bàn phường | Phân công công chức, **kiểm tra dự thảo** trước khi trình ký |
| Xã | `cb.khanhhau` | Công chức phụ trách CĐS | Địa bàn phường | Xử lý, trình dự thảo, **lập phiếu tự đánh giá** |
| Xã | `qt.khanhhau` | Quản trị hệ thống cấp phường | Địa bàn phường | Cấp / khóa tài khoản cán bộ phường & trường (không xử lý văn bản) |
| Trường | `truong.thcs` | Hiệu trưởng THCS Khánh Hậu | Trường mình | Tiếp nhận, phân công, ký & phát hành báo cáo, nộp phiếu tự đánh giá |
| Trường | `gv.thcs` | Giáo viên phụ trách CNTT | Trường mình | Xử lý, trình hiệu trưởng, khai phiếu tự đánh giá |
| Khác | `am01`, `am02` | Nhân viên AM (doanh nghiệp viễn thông) | Đơn vị được phân công | Cơ hội dịch vụ, gia hạn, kế hoạch chăm sóc |
| Hệ thống | `admin` | Quản trị hệ thống | Tài khoản, vai trò, danh mục, nhật ký | Không xem số liệu, không xử lý văn bản; có "Xem dưới vai trò" (chỉ xem) để hỗ trợ |

> Dữ liệu là **mô phỏng** (247 đơn vị, 44 xã/phường, 8 quý 2025-Q1 → 2026-Q4). Tên đơn vị lấy theo địa danh, số liệu sinh ngẫu nhiên có kiểm soát.

## 📖 Hướng dẫn sử dụng

### Giao diện chung

- **Bàn làm việc** (trang đầu sau khi đăng nhập): các *hàng đợi việc cần làm* của đúng chức danh đó, mỗi việc có nút thao tác nhanh
  (Tiếp nhận, Phân công, Kiểm tra, Ký duyệt, Phát hành, Thẩm định…). Số trên đầu mỗi hàng đợi là số việc tồn.
- **Menu trái** chỉ hiện chức năng người đó được dùng, chia nhóm: Công việc · Giám sát · Đánh giá · Hoạch định · Dữ liệu · Quản trị.
- **Chuông thông báo** (góc phải trên): có việc mới đến, bị trả lại, được xác nhận… Bấm vào để mở việc.
- **Tài khoản của tôi**: đổi mật khẩu, xem và đăng xuất các phiên đăng nhập khác.
- Thử nhanh: đăng xuất → đăng nhập tài khoản khác ở trang đăng nhập.

### Kịch bản 1 – Văn bản giao việc đi từ Tỉnh xuống Xã, xuống Trường (theo NĐ 30/2020)

| # | Đăng nhập | Làm gì | Ở đâu |
|---|---|---|---|
| 1 | `lanhdao.tinh` | Giao nhiệm vụ cho UBND phường Khánh Hậu (nhập trích yếu, số văn bản, hạn) | Văn bản & nhiệm vụ → **Giao nhiệm vụ** |
| 2 | `vanthu.khanhhau` | **Tiếp nhận** văn bản → hệ thống cấp *số đến* | Bàn làm việc → “Văn bản đến chờ tiếp nhận” |
| 3 | `khanhhau` | **Phân công** Phòng VH-XH, ghi ý kiến chỉ đạo (bút phê); nếu cần số liệu của trường thì **Giao tiếp cho trường** | Bàn làm việc → “Chờ phân công” / mở nhiệm vụ |
| 4 | `tp.khanhhau` | Phân công công chức cụ thể | Bàn làm việc |
| 5 | `cb.khanhhau` | Cập nhật tiến độ, **Trình dự thảo** | Bàn làm việc → “Việc đang xử lý” |
| 6 | `tp.khanhhau` | **Kiểm tra** dự thảo → trình lãnh đạo ký (hoặc **Trả về**) | Bàn làm việc → “Dự thảo chờ kiểm tra” |
| 7 | `khanhhau` | **Ký duyệt** (hoặc trả về xử lý) | Bàn làm việc → “Văn bản chờ ký duyệt” |
| 8 | `vanthu.khanhhau` | **Cấp số & phát hành** → hệ thống tự cấp số đi `n/BC-UBND`, ghi sổ đi, gửi lên tỉnh | Bàn làm việc → “chờ cấp số, phát hành” |
| 9 | `lanhdao.tinh` hoặc `vp.ubndtinh` | Kiểm tra báo cáo: **Xác nhận hoàn thành** hoặc **Trả lại** yêu cầu bổ sung | Bàn làm việc → “Báo cáo cấp dưới chờ xác nhận” |

- Ở bước 3, phường chỉ gửi báo cáo lên tỉnh được khi **các trường được giao tiếp đã hoàn thành**. Phía trường: `truong.thcs` tiếp nhận, giao `gv.thcs` xử lý, hiệu trưởng ký là hệ thống tự phát hành (hiệu trưởng kiêm văn thư).
- Mở một nhiệm vụ → tab **Sơ đồ luồng Tỉnh → Xã → Trường** để xem tiến độ từng cấp; tab **Lịch sử xử lý** ghi lại ai làm gì, lúc nào.
- **Sổ văn bản đến / đi** (menu Công việc, dành cho văn thư và lãnh đạo): tra cứu theo năm, **Xuất sổ** ra Excel.
- Dữ liệu mẫu đã có sẵn một dự thảo chờ `tp.khanhhau` kiểm tra và một văn bản đã ký chờ `vanthu.khanhhau` phát hành – đăng nhập là thấy ngay.

### Kịch bản 2 – Đánh giá mức độ chuyển đổi số của kỳ (tự đánh giá → thẩm định → công bố)

| # | Đăng nhập | Làm gì | Ở đâu |
|---|---|---|---|
| 1 | `cb.khanhhau` | Khai giá trị từng tiêu chí + **minh chứng** (đã gợi ý sẵn số liệu kỳ trước) → **Lưu nháp** | Menu **Tự đánh giá CĐS** |
| 2 | `khanhhau` | Kiểm tra phiếu → **Duyệt & nộp** (cần khai đủ tiêu chí, minh chứng ≥ 1/2 số tiêu chí) | Tự đánh giá CĐS |
| 3 | `skhcn` | Mở phiếu, đối chiếu minh chứng; chỗ nào chưa đúng thì nhập **Giá trị thẩm định** khác → **Phê duyệt**, hoặc **Yêu cầu giải trình** (đơn vị sửa và nộp lại) | Menu **Thẩm định & công bố** |
| 4 | `lanhdao.tinh` | Khi không còn phiếu chờ thẩm định: **Công bố kết quả**, nhập số quyết định | Thẩm định & công bố |

- Phiếu của **trường học** do `sgddt` thẩm định; phiếu của **cơ quan hành chính** do `skhcn` thẩm định.
- Phê duyệt xong, số liệu tự đi qua kho dữ liệu Bronze → Silver → Gold và tính lại DTI. Trang **Tổng quan CĐS** ghi rõ *Tạm tính* hay *Kết quả chính thức · QĐ …*.

### Kịch bản 3 – Giám sát, đánh giá, hoạch định (lãnh đạo)

1. `lanhdao.tinh` → **Tổng quan CĐS**: chỉ số DTI trung bình, phân bố 5 mức, xu hướng theo kỳ; lọc theo loại hình hoặc xã/phường.
2. **Xếp hạng & so sánh**: xếp hạng đơn vị, so sánh nhiều đơn vị theo 7 trụ cột.
3. **Cảnh báo & ưu tiên**: đơn vị điểm thấp, giảm mạnh, thiếu dữ liệu, danh sách cần ưu tiên hỗ trợ.
4. **Phân cụm & dự báo**: nhóm đơn vị có đặc điểm giống nhau (K-Means), dự báo xu hướng kỳ sau.
5. **Hỗ trợ hoạch định** → chọn nhóm giải pháp → **Lập kế hoạch cải thiện**; đơn vị cập nhật tiến độ ở **Kế hoạch cải thiện**.
6. **Báo cáo**: xuất Excel (DTI, nhiệm vụ, xu hướng).

### Kịch bản 4 – Dữ liệu (`skhcn`)

1. **Tích hợp dữ liệu** → **Tải file mẫu** → điền số liệu → kéo thả file vào ô tải lên (thử file có lỗi `sample_data/cap_nhat_bo_sung_dang_dai.csv`).
2. Xem lô dữ liệu: bản ghi gốc (Bronze), giá trị hợp lệ / bị loại kèm lý do (Silver), điểm đã tính (Gold).
3. **Đồng bộ dữ liệu vận hành** (tỷ lệ nhiệm vụ đúng hạn, hạ tầng, dịch vụ) – hệ thống tự tính lại chỉ số DTI.
4. **Bộ tiêu chí DTI**: sửa trọng số, mục tiêu, bật/tắt tiêu chí.

### Kịch bản 5 – Quản trị (`admin`, `qt.khanhhau`)

- `admin`: **Tài khoản người dùng** (tạo, khóa, mật khẩu tạm, nhập/xuất Excel, chuyển giao công việc khi cán bộ nghỉ), **Vai trò & phân quyền**,
  **Danh mục đơn vị / địa bàn**, **Kỳ đánh giá** (khóa số liệu), **Thông báo hệ thống**, **Giám sát & sao lưu**, **Nhật ký & bảo mật**, **Tích hợp API**.
- **Xem dưới vai trò**: admin chọn một tài khoản để xem đúng giao diện của người đó (chỉ xem, không thao tác thay), bấm **Trở về quản trị** để quay lại.
- **Thiết lập tỉnh mới**: 7 bước triển khai cho tỉnh khác (xem [docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md](docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md)).
- `qt.khanhhau`: chỉ quản lý được tài khoản của phường và các trường trên địa bàn, không gán được vai trò cấp tỉnh.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [docs/THIET_KE_HE_THONG.md](docs/THIET_KE_HE_THONG.md) | Thiết kế, kiến trúc, mô hình dữ liệu, phương pháp DTI, phân quyền |
| [docs/DOI_CHIEU_DE_CUONG.md](docs/DOI_CHIEU_DE_CUONG.md) | Đối chiếu từng yêu cầu đề cương ↔ chức năng, mã nguồn, kiểm chứng |
| [docs/KET_QUA_THUC_NGHIEM.md](docs/KET_QUA_THUC_NGHIEM.md) | Kết quả thực nghiệm (sinh lại: `python -m scripts.report_experiment`) |
| [docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md](docs/HUONG_DAN_TRIEN_KHAI_TINH_MOI.md) | Triển khai cho tỉnh/thành mới |
| [docs/HUONG_DAN_POWER_BI.md](docs/HUONG_DAN_POWER_BI.md) | Kết nối Power BI với các view `gold.v_bi_*` |

## Cấu trúc thư mục

```
start.bat / setup.bat / export-db.bat   # chạy · cài lại · xuất dữ liệu (xem phần "Chạy trên máy mới")
deploy/                  # script PowerShell mà các file .bat gọi
database/
  dti_platform.sql       # toàn bộ dữ liệu (máy mới tự nạp)
  uploads/               # tệp đính kèm của nhiệm vụ
backend/
  app/
    models.py            # mô hình dữ liệu 4 schema (public/bronze/silver/gold)
    security.py          # JWT, RBAC, phạm vi dữ liệu, nhật ký
    services/pipeline.py # Bronze → Silver (làm sạch, chuẩn hóa, đồng bộ dữ liệu vận hành)
    services/scoring.py  # Silver → Gold (DTI, xếp hạng, cảnh báo, ưu tiên, đề xuất)
    services/ml.py       # K-Means + dự báo xu hướng
    routers/             # API: auth, admin, catalog, analytics, data, tasks, assessments, workspace, am, plans, reports…
  scripts/seed.py        # sinh lại dữ liệu mô phỏng (chạy qua đúng pipeline)
  scripts/smoke_test.py  # kiểm thử API nhiều vai trò (luồng văn bản NĐ 30)
  scripts/test_*.py      # kiểm thử tự đánh giá, quản trị, phân quyền, đề cương…
frontend/src/pages/      # các màn hình React
sample_data/             # file CSV mẫu để thử chức năng nhập dữ liệu
docs/                    # tài liệu thiết kế
```
