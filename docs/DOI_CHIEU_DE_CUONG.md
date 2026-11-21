# Đối chiếu đề cương ↔ hệ thống đã xây dựng

Bảng truy vết từng yêu cầu trong đề cương tới chức năng, mã nguồn và cách kiểm chứng.
Ký hiệu: ✅ đáp ứng đầy đủ · 🟡 đáp ứng có điều chỉnh (có giải thích).

## 1. Mục tiêu cụ thể (mục 2.2)

| # | Mục tiêu | Mức | Chức năng trên hệ thống | Mã nguồn chính | Kiểm chứng |
|---|---|---|---|---|---|
| 1 | Quản lý tập trung thông tin cơ quan hành chính, cơ sở giáo dục, địa bàn, dịch vụ/giải pháp công nghệ | ✅ | *Đơn vị* (hồ sơ, hạ tầng, dịch vụ đang dùng), *Danh mục đơn vị / địa bàn* (quản trị), *Danh mục dịch vụ số* (thêm/sửa), nhập danh mục Excel | `routers/catalog.py`, `admin.py`, `admin_ops.py`, `pages/Units.tsx`, `UnitDetail.tsx`, `Services.tsx` | `test_outline_features` (1), `test_new_province` |
| 2 | Quản lý người dùng, phân quyền theo vai trò, cấp quản lý, phạm vi dữ liệu | ✅ | 14 vai trò = cấp × chức danh; 5 phạm vi dữ liệu (toàn tỉnh / ngành GD / xã / đơn vị / AM); quản trị phân cấp tỉnh – xã | `security.py`, `routers/admin.py`, `pages/Admin.tsx` | `smoke_test`, `test_admin_ops` |
| 3 | Quy trình tiếp nhận, chuẩn hóa, tổ chức dữ liệu | ✅ | Pipeline Bronze → Silver → Gold: nhập CSV/Excel, đồng bộ dữ liệu vận hành, API tích hợp; làm sạch, loại lỗi kèm lý do | `services/pipeline.py`, `routers/data.py`, `integration.py` | `KET_QUA_THUC_NGHIEM.md` §2 |
| 4 | Cơ sở dữ liệu phục vụ quản lý và khai thác | ✅ | PostgreSQL 4 schema `public / bronze / silver / gold` + view BI `gold.v_bi_*` | `models.py`, `services/bi.py` | §1 báo cáo thực nghiệm |
| 5 | Dashboard trực quan | ✅ | *Tổng quan CĐS*, *Bàn làm việc* theo chức danh, biểu đồ xu hướng, radar trụ cột, phân bố | `pages/Dashboard.tsx`, `Workspace.tsx` | Trình duyệt |
| 6 | Bộ tiêu chí đánh giá | ✅ | 7 trụ cột, 24 tiêu chí (áp dụng theo loại hình), trọng số & mục tiêu chỉnh được | `scripts/seed.py` (CRITERIA), `pages/Framework.tsx` | — |
| 7 | Chỉ số tổng hợp từng đơn vị | ✅ | Digital Transformation Score 0–100, 5 mức, hạng toàn tỉnh & trong loại hình, Δ kỳ trước | `services/scoring.py` | §3 báo cáo thực nghiệm |
| 8 | Phân tích, so sánh giữa đơn vị / khu vực | ✅ | *Xếp hạng & so sánh* (đơn vị, xã/phường, so sánh tối đa 5 đơn vị), báo cáo diễn biến theo thời gian | `routers/analytics.py`, `pages/Ranking.tsx`, `reports.py` (`trend.xlsx`) | `test_outline_features` (5) |
| 9 | Xác định nhóm đơn vị cần ưu tiên | ✅ | Cảnh báo 6 loại, chỉ số ưu tiên 0–100, phân cụm K-Means | `scoring.py`, `services/ml.py`, `pages/Alerts.tsx`, `Clusters.tsx` | §4–5 báo cáo thực nghiệm |
| 10 | Đề xuất nhóm giải pháp phù hợp | ✅ | 16 nhóm giải pháp, luật kích hoạt theo tiêu chí, mức ưu tiên, dịch vụ còn thiếu | `scoring.recommend` | §4 báo cáo thực nghiệm |
| 11 | Hệ thống báo cáo, thống kê các cấp | ✅ | 3 báo cáo Excel (kết quả DTI, diễn biến theo thời gian, tiến độ nhiệm vụ), xuất kế hoạch, xuất nhật ký, view Power BI – tất cả theo phạm vi phân quyền | `routers/reports.py`, `plans.py`, `pages/Reports.tsx` | `test_outline_features` (5) |
| 12 | Thử nghiệm trên bộ dữ liệu nghiên cứu, đánh giá khả năng đáp ứng | ✅ | Bộ dữ liệu mô phỏng 247 đơn vị × 8 quý; 6 bộ kiểm thử tự động; báo cáo thực nghiệm sinh tự động | `scripts/*`, `docs/KET_QUA_THUC_NGHIEM.md` | Chạy lại các script |

## 2. Phạm vi người dùng (mục 3.3)

| Nhóm người dùng | Quyền trong đề cương | Mức | Vai trò / chức năng tương ứng |
|---|---|---|---|
| **Quản trị viên** | Quản lý người dùng | ✅ | Tài khoản người dùng (cấp, khóa, mật khẩu tạm, nhập/xuất Excel, chuyển giao), phiên đăng nhập |
| | Quản lý vai trò | ✅ | Vai trò & phân quyền (tạo vai trò, gán quyền theo phân hệ, phạm vi dữ liệu), ma trận vai trò |
| | Quản lý đơn vị | ✅ | Danh mục đơn vị, địa bàn, nhập danh mục Excel |
| | Quản lý dữ liệu | 🟡 | Quản lý **ở mức hệ thống**: kỳ đánh giá & khóa số liệu, sao lưu CSDL, khóa API tích hợp, tham số hệ thống. Việc nhập/chỉnh **số liệu nghiệp vụ** giao cho vai trò *Chuyên viên dữ liệu Sở KH&CN* theo nguyên tắc tách biệt nhiệm vụ (quản trị không sửa số liệu đánh giá) |
| | Theo dõi hoạt động hệ thống | ✅ | Nhật ký & cảnh báo bảo mật, giám sát (CSDL, lỗi, phiên), bàn làm việc quản trị |
| **Cấp quản lý** (Lãnh đạo tỉnh, VP UBND tỉnh, Lãnh đạo Sở GD&ĐT, Lãnh đạo xã) | Theo dõi dữ liệu theo phạm vi | ✅ | Phạm vi `all` / `giao_duc` / `region` |
| | Xem dashboard, báo cáo | ✅ | Tổng quan CĐS, Báo cáo |
| | Đánh giá tình hình CĐS | ✅ | Xếp hạng, phân cụm, hồ sơ đơn vị |
| | Theo dõi đơn vị cần ưu tiên | ✅ | Cảnh báo & ưu tiên |
| **Cơ quan hành chính** (Lãnh đạo cơ quan cấp tỉnh, UBND xã) | Theo dõi thông tin đơn vị, hạ tầng, dịch vụ số | ✅ | Hồ sơ đơn vị (thông tin, hạ tầng, dịch vụ), tự khai báo hạ tầng |
| | Xem chỉ số CĐS, đề xuất cải thiện | ✅ | DTI, trụ cột, tiêu chí, đề xuất, lập kế hoạch cải thiện của cơ quan |
| **Cơ sở giáo dục** (Hiệu trưởng, giáo viên CNTT) | Thông tin trường, hạ tầng CNTT, giải pháp công nghệ | ✅ | Hồ sơ trường, khai báo hạ tầng, dịch vụ đang dùng |
| | Mức độ CĐS, vấn đề cần cải thiện | ✅ | DTI, đề xuất, cập nhật tiến độ hạng mục kế hoạch |
| **Nhân viên AM** | Theo dõi đơn vị phụ trách | ✅ | AM Intelligence – danh mục đơn vị |
| | Phân tích tình trạng sử dụng dịch vụ | ✅ | Mức khai thác, tỷ lệ phủ dịch vụ, khai thác thấp |
| | Nhu cầu tiềm năng, cơ hội phát triển dịch vụ | ✅ | Cơ hội dịch vụ (từ đề xuất CĐS), gia hạn |
| | Hỗ trợ xây dựng kế hoạch chăm sóc | ✅ | Kế hoạch chăm sóc: thêm/sửa, **gợi ý tự động từ dữ liệu**, ghi kết quả |

Ngoài đề cương, hệ thống bổ sung các vai trò nghiệp vụ văn thư / trưởng phòng / công chức / quản trị xã để mô phỏng luồng
xử lý văn bản liên thông Tỉnh → Xã → Trường (tham chiếu quy trình VBĐH).

**Bổ sung để mỗi vai trò khép kín một quy trình thực tế:**

| Quy trình | Bước | Vai trò thực hiện | Chức năng trong hệ thống |
|---|---|---|---|
| Văn bản đến (NĐ 30/2020) | Tiếp nhận, đăng ký số đến | Văn thư / Hiệu trưởng / Lãnh đạo cơ quan | Bàn làm việc → "Văn bản đến chờ tiếp nhận"; Sổ văn bản đến |
| | Cho ý kiến chỉ đạo, phân công | Lãnh đạo xã, Trưởng phòng | Phân công + bút phê (lưu vào sổ đến) |
| Văn bản đi (NĐ 30/2020) | Soạn thảo, trình | Công chức / Giáo viên | Trình dự thảo |
| | Kiểm tra nội dung, thể thức | Trưởng phòng | Hàng đợi "Dự thảo chờ kiểm tra" (kiểm tra / trả về) |
| | Ký duyệt | Lãnh đạo xã / Hiệu trưởng / Lãnh đạo cơ quan | Hàng đợi "Văn bản chờ ký duyệt" |
| | Cấp số, ngày, đăng ký sổ đi, phát hành | Văn thư (hiệu trưởng, lãnh đạo cơ quan kiêm) | Hàng đợi "chờ cấp số, phát hành"; Sổ văn bản đi + xuất Excel |
| Đánh giá CĐS theo kỳ | Lập phiếu tự đánh giá + minh chứng | Công chức xã / Giáo viên / Lãnh đạo cơ quan | Tự đánh giá CĐS |
| | Duyệt, nộp | Lãnh đạo xã / Hiệu trưởng / Lãnh đạo cơ quan | Tự đánh giá CĐS → Duyệt & nộp |
| | Thẩm định (chấp nhận, điều chỉnh, yêu cầu giải trình) | Sở KH&CN (hành chính), Sở GD&ĐT (giáo dục) | Thẩm định & công bố |
| | Công bố kết quả chính thức bằng quyết định, khóa số liệu | Lãnh đạo UBND tỉnh | Thẩm định & công bố → Công bố kết quả |

## 3. Phương pháp & công nghệ (mục 4)

| Mục | Nội dung đề cương | Mức | Thực hiện |
|---|---|---|---|
| 4.1 | Web, đăng nhập, phân quyền; React + TypeScript, Python + FastAPI, JWT/RBAC | ✅ | React 18 + TS + Ant Design; FastAPI; JWT có mã phiên (thu hồi được) + RBAC + phạm vi dữ liệu theo dòng |
| 4.2 | Quản lý đơn vị & dữ liệu; PostgreSQL + FastAPI + SQL | ✅ | PostgreSQL 17, SQLAlchemy 2, truy vấn tổng hợp SQL |
| 4.3 | Tiếp nhận, làm sạch, chuẩn hóa, biến đổi; mô hình Bronze–Silver–Gold; Python, Pandas, SQL, PySpark *tùy quy mô* | 🟡 | Python + Pandas + SQL. **PySpark không dùng** vì quy mô thực nghiệm (~40 nghìn giá trị/8 kỳ, tính Gold 1 kỳ < 1 giây) không cần xử lý phân tán; kiến trúc tách tầng cho phép thay bước Silver/Gold bằng PySpark khi quy mô cấp quốc gia (ghi ở Hướng phát triển) |
| 4.4 | Phân tích theo đơn vị, địa bàn, loại hình, thời gian; Plotly / thư viện biểu đồ React; Power BI *có thể* | ✅ | Recharts (thư viện biểu đồ React); bộ view `gold.v_bi_*` để Power BI kết nối – xem `HUONG_DAN_POWER_BI.md` |
| 4.5 | Dữ liệu → tiêu chí → tính chỉ số → DTI → phân loại; so sánh, theo dõi theo thời gian | ✅ | `scoring.compute_period`, lịch sử DTI từng đơn vị |
| 4.6 | Đơn vị thấp, nhóm tiêu chí hạn chế, khu vực cần quan tâm; bảng xếp hạng, dashboard, cảnh báo | ✅ | Cảnh báo LOW_SCORE / SCORE_DROP / WEAK_PILLAR / OVERDUE_TASK / MISSING_DATA / EXPIRING_SERVICE, xếp hạng xã/phường |
| 4.7 | Hiện trạng → vấn đề → ưu tiên → đề xuất → **hỗ trợ hoạch định / xây dựng kế hoạch** | ✅ | Hỗ trợ hoạch định + **Kế hoạch cải thiện**: lập từ đề xuất, điều chỉnh, ban hành, đơn vị cập nhật tiến độ, so sánh điểm mốc với DTI kỳ sau, xuất Excel |
| 4.8 | Hỗ trợ AM với dữ liệu dịch vụ | ✅ | AM Intelligence + kế hoạch chăm sóc |
| 4.9 | ML hỗ trợ: phân nhóm, phân loại, dự đoán, gợi ý; chọn thuật toán sau phân tích dữ liệu; đánh giá kết quả | ✅ | **Phân nhóm**: K-Means (chọn k bằng silhouette/elbow); **phân loại**: 5 mức theo ngưỡng DTI; **dự đoán**: hồi quy xu hướng, backtest MAE/RMSE/MAPE so với mô hình cơ sở; **gợi ý**: luật đề xuất giải pháp & dịch vụ |
| — | Khảo sát, phân tích nhu cầu; thực nghiệm; đánh giá tính chính xác, hợp lý | ✅ | `THIET_KE_HE_THONG.md`, `KET_QUA_THUC_NGHIEM.md`, bộ kiểm thử |

## 4. Kết quả dự kiến (mục 6)

| Kết quả dự kiến | Mức | Ghi chú |
|---|---|---|
| Nền tảng quản trị dữ liệu, phân quyền theo nhóm người dùng | ✅ | |
| Quy trình tích hợp, làm sạch, chuẩn hóa Bronze – Silver – Gold | ✅ | |
| Bộ tiêu chí & DTI; phân loại, so sánh, theo dõi theo đơn vị, địa bàn, thời gian | ✅ | |
| Xác định đơn vị/lĩnh vực ưu tiên, nhóm giải pháp tham khảo hỗ trợ kế hoạch | ✅ | |
| Dashboard trực quan & báo cáo tổng hợp | ✅ | |
| Thử nghiệm trên **bộ dữ liệu VNPT**, hỗ trợ VNPT/AM | 🟡 | Chưa có bộ dữ liệu VNPT thật trong quá trình xây dựng → thực nghiệm trên **dữ liệu mô phỏng** cùng cấu trúc (đề cương mục 3.2 cho phép). Khi có dữ liệu VNPT: nhập qua *Tích hợp dữ liệu* (CSV/Excel) hoặc *API tích hợp* `POST /api/integration/metrics` – không cần sửa mã |

## 5. Dàn ý báo cáo (Chương 2–3) ↔ tài liệu sẵn có

| Mục báo cáo | Tài liệu / nguồn |
|---|---|
| 2.1–2.3 Phân tích yêu cầu, đối tượng, nghiệp vụ | `THIET_KE_HE_THONG.md` §1, §4 (vai trò), mục này |
| 2.4 Kiến trúc tổng thể | `THIET_KE_HE_THONG.md` §2 |
| 2.5 Mô hình dữ liệu | `THIET_KE_HE_THONG.md` §3, `backend/app/models.py` |
| 2.6 Quy trình xử lý dữ liệu | `THIET_KE_HE_THONG.md` §5 |
| 2.7–2.8 Phương pháp đánh giá, xây dựng chỉ số | `THIET_KE_HE_THONG.md` §6 |
| 2.9 Phương pháp phân tích | §7, §10 |
| 2.10 Hỗ trợ hoạch định | §8 + Kế hoạch cải thiện |
| 2.11 Kiểm thử, đánh giá | `KET_QUA_THUC_NGHIEM.md` §6 |
| 3.1 Môi trường triển khai | `README.md`, `HUONG_DAN_TRIEN_KHAI_TINH_MOI.md` §0 |
| 3.2–3.11 Xây dựng các thành phần | Mã nguồn theo bảng §1 |
| 3.12–3.13 Thực nghiệm, đánh giá | `KET_QUA_THUC_NGHIEM.md` (sinh lại bằng `python -m scripts.report_experiment`) |
| 3.14 Hạn chế | `THIET_KE_HE_THONG.md` §12 + các mục 🟡 ở trên |
