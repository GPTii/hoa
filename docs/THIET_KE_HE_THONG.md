# Thiết kế hệ thống & cách hoạt động

Tài liệu này bám theo cấu trúc Chương 2–3 của đề cương, dùng làm khung viết báo cáo.

## 1. Bối cảnh nghiệp vụ (Tây Ninh – chính quyền 2 cấp)

```
                 UBND TỈNH TÂY NINH  (Chủ tịch, các Phó Chủ tịch)
                         │  giao nhiệm vụ / nhận báo cáo
                 VĂN PHÒNG UBND TỈNH  (tiếp nhận – tham mưu – theo dõi – đôn đốc)
                         │
     SỞ, BAN, NGÀNH  ◄───┼───►  trao đổi trực tiếp theo chuyên môn
   (KH&CN, GD&ĐT, Nội vụ…)│
                         ▼
                 UBND XÃ / PHƯỜNG   (không còn cấp huyện)
        Văn thư → Chủ tịch/PCT → Lãnh đạo phòng → Công chức
                         │
                 TRƯỜNG MẦM NON / TIỂU HỌC / THCS (do xã quản lý), THPT (do Sở GD&ĐT quản lý)
```

Hệ thống **không thay thế** VBĐH (vbdh.tayninh.gov.vn) mà khai thác dữ liệu điều hành (nhiệm vụ, tiến độ, đúng hạn)
cùng dữ liệu khảo sát, hạ tầng, dịch vụ số để **đánh giá – cảnh báo – hoạch định** chuyển đổi số.

### Luồng liên thông 3 cấp Tỉnh → Xã/Phường → Trường học

```
UBND tỉnh (NV gốc, hạn 09/12) ──► UBND phường Khánh Hậu: tiếp nhận → phân công Phòng VH-XH
                                     │  GIAO TIẾP (nhiệm vụ con, hạn ≤ hạn cấp trên)
                                     ├──► Trường Mầm non  : tiếp nhận → báo cáo → phường xác nhận ✔
                                     ├──► Trường Tiểu học : tiếp nhận → báo cáo → (chờ phường xác nhận)
                                     └──► Trường THCS     : đang xử lý
                                     │  tiến độ phường tự cập nhật = số trường xong / tổng × 90%
                                     ▼  chỉ khi TẤT CẢ trường đã xong mới được gửi báo cáo tổng hợp
UBND tỉnh / VP UBND tỉnh xác nhận hoàn thành ◄── báo cáo tổng hợp của phường
```

- Bảng `tasks.parent_assignment_id` liên kết nhiệm vụ con với lượt giao của cấp trên → dựng được cây nhiều cấp (`GET /api/tasks/{id}/tree`).
- Cấp dưới của xã = trường Mầm non, Tiểu học, THCS trên địa bàn (do xã quản lý). Trường THPT do Sở GD&ĐT quản lý nên tỉnh/Sở giao thẳng.
- Kiểm tra nghiệp vụ: phải tiếp nhận trước khi giao tiếp; hạn cấp dưới ≤ hạn cấp trên; chỉ giao cho đơn vị cấp dưới của mình; chỉ chính đơn vị nhận mới giao tiếp.
- Sở chuyên ngành vẫn có thể trao đổi trực tiếp với trường/xã theo chuyên môn (Luồng 2 trong quy trình).

Hai luồng được tách rõ đúng như quy trình:
1. **Quản lý văn bản**: ban hành → phát hành → liên thông → tiếp nhận → xử lý (đặc trưng của VBĐH; hệ thống ghi số/ký hiệu văn bản giao & văn bản báo cáo).
2. **Quản lý nhiệm vụ**: giao việc → tiếp nhận → phân công → cập nhật tiến độ → báo cáo → **cơ quan giao xác nhận** → kết thúc.
   *Đã nhận văn bản ≠ hoàn thành; đã gửi báo cáo ≠ hoàn thành.*

## 2. Kiến trúc tổng thể

```
┌───────────── Trình duyệt (React + TS + Ant Design + Recharts) ─────────────┐
│ Tổng quan · Đơn vị · Xếp hạng · Cảnh báo · Phân cụm · Hoạch định · Nhiệm vụ │
│ AM Intelligence · Tích hợp dữ liệu · Bộ tiêu chí · Báo cáo · Quản trị       │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ REST/JSON + JWT Bearer
┌──────────────────────────────▼──────────────────────────────────────────────┐
│ FastAPI                                                                      │
│  security.py : xác thực JWT → RBAC (quyền) → phạm vi dữ liệu (row-level)     │
│  routers/    : auth · admin · catalog · analytics · data · tasks · am · reports│
│  services/   : pipeline (Bronze→Silver) · scoring (→Gold) · ml (K-Means, dự báo)│
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ SQLAlchemy 2 + psycopg 3
┌──────────────────────────────▼──────────────────────────────────────────────┐
│ PostgreSQL 17 — 1 database, 4 schema                                         │
│  public : regions, units, users, roles, permissions, criteria, tasks…        │
│  bronze : ingest_batches, raw_records (JSONB nguyên trạng)                   │
│  silver : unit_metrics (đơn vị–kỳ–tiêu chí–giá trị), rejected_records        │
│  gold   : criterion/pillar/dti_scores, region_scores, alerts,                │
│           priority_units, recommendations, unit_clusters                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Vì sao PostgreSQL thay MongoDB:** dữ liệu có quan hệ chặt (địa bàn → đơn vị → chỉ số → kỳ), cần JOIN/GROUP BY
để tổng hợp theo nhiều chiều, cần ràng buộc toàn vẹn (khóa ngoại, UNIQUE đơn vị–kỳ–tiêu chí) và giao dịch
khi tính lại điểm. Phần dữ liệu "phi cấu trúc" (dòng thô từ file nguồn) vẫn lưu linh hoạt bằng **JSONB** ở tầng Bronze,
nên không mất lợi thế của document store.

## 3. Mô hình dữ liệu (rút gọn)

| Nhóm | Bảng | Ghi chú |
|---|---|---|
| Tổ chức | `regions` (tinh/phuong/xa), `units` (hanh_chinh/giao_duc; category; level tinh/xa; parent_unit_id) | Cây tổ chức 2 cấp |
| Người dùng | `users`, `roles` (data_scope), `permissions`, `role_permissions`, `am_assignments`, `audit_logs` | RBAC + phạm vi |
| Hạ tầng & dịch vụ | `unit_infra`, `service_catalog`, `unit_services` (trạng thái, hạn, mức khai thác, phí) | Nguồn cho AM |
| Bộ tiêu chí | `periods`, `pillars` (7 trụ cột, trọng số), `criteria` (24 tiêu chí: kiểu, mục tiêu, trọng số, nguồn), `solution_groups` (16 nhóm, tiêu chí kích hoạt, dịch vụ liên quan) | Cấu hình được trên giao diện |
| Điều hành | `tasks` (văn bản giao, hạn, độ khẩn), `task_assignments` (trạng thái tại từng đơn vị), `task_logs` | Liên thông VBĐH |
| Bronze | `ingest_batches`, `raw_records(payload JSONB)` | Truy vết nguồn |
| Silver | `unit_metrics` UNIQUE(unit, period, criterion), `rejected_records` | Dữ liệu sạch |
| Gold | `criterion_scores`, `pillar_scores`, `dti_scores`, `region_scores`, `alerts`, `priority_units`, `recommendations`, `unit_clusters` | Phục vụ phân tích |

## 4. Phân quyền (RBAC + phạm vi dữ liệu)

Mỗi request: **JWT → người dùng → vai trò → (1) danh sách quyền** (vd `data.import`, `task.assign`) **→ (2) phạm vi dữ liệu**:

| data_scope | Ý nghĩa | Vai trò mẫu |
|---|---|---|
| `all` | Toàn tỉnh | Quản trị, Lãnh đạo tỉnh, VP UBND tỉnh, Sở |
| `region` | Mọi đơn vị trên địa bàn xã/phường của người dùng | Lãnh đạo UBND xã/phường |
| `unit` | Chỉ đơn vị mình | Cơ quan hành chính, Cơ sở giáo dục |
| `assigned` | Các đơn vị được phân công chăm sóc | Nhân viên AM |

Ngoài ra `giao_duc` = toàn bộ cơ sở giáo dục trong tỉnh (cho Sở GD&ĐT).

### Vai trò = Cấp × Chức danh (14 vai trò)

**Văn bản & nhiệm vụ** (quy trình NĐ 30/2020/NĐ-CP về công tác văn thư):

| Cấp | Vai trò | Phạm vi | Giao | Tiếp nhận (sổ đến) | Phân công + bút phê | Xử lý, trình | Kiểm tra dự thảo | Ký duyệt | Cấp số, phát hành (sổ đi) | Xác nhận |
|---|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Tỉnh | Lãnh đạo UBND tỉnh | all | ✓ | | | | | | | ✓ |
| Tỉnh | Chuyên viên VP UBND tỉnh | all | | | | | | | | ✓ |
| Sở | Chuyên viên dữ liệu Sở KH&CN | all | | | | | | | | |
| Sở | Lãnh đạo Sở GD&ĐT | giao_duc | ✓ | | | | | | | ✓ |
| Sở | Lãnh đạo cơ quan cấp tỉnh | unit | | ✓ | ✓ | ✓ | | ✓ | ✓ | |
| Xã | Lãnh đạo UBND xã | region | ✓ | | ✓ | | | ✓ | | ✓ |
| Xã | Văn thư | unit | | ✓ | | | | | ✓ | |
| Xã | Trưởng phòng chuyên môn | region | | | ✓ | ✓ | ✓ | | | |
| Xã | Công chức chuyên môn | region | | | | ✓ | | | | |
| Trường | Hiệu trưởng (kiêm văn thư) | unit | | ✓ | ✓ | | | ✓ | ✓ | |
| Trường | Giáo viên / cán bộ CNTT | unit | | | | ✓ | | | | |

**Đánh giá mức độ chuyển đổi số** (đơn vị tự đánh giá → thẩm định → công bố):

| Vai trò | Lập phiếu (`assess.prepare`) | Duyệt, nộp (`assess.submit`) | Thẩm định (`assess.review`) | Công bố (`assess.publish`) |
|---|:-:|:-:|:-:|:-:|
| Công chức xã / Giáo viên | ✓ | | | |
| Lãnh đạo UBND xã / Hiệu trưởng | (sửa được) | ✓ | | |
| Lãnh đạo cơ quan cấp tỉnh | ✓ | ✓ | | |
| Chuyên viên dữ liệu Sở KH&CN | | | ✓ cơ quan hành chính | |
| Lãnh đạo Sở GD&ĐT | | | ✓ cơ sở giáo dục | |
| Lãnh đạo UBND tỉnh | | | | ✓ |

Ngoài ra: Quản trị xã (cấp tài khoản trong địa bàn), Nhân viên AM (đơn vị phụ trách), Quản trị hệ thống (chỉ vận hành, không nghiệp vụ).

#### Luồng văn bản trong một đơn vị nhận (NĐ 30/2020)

```
Văn bản đến ─► VĂN THƯ tiếp nhận, cấp SỐ ĐẾN (sổ văn bản đến, liên tiếp theo năm)
            ─► LÃNH ĐẠO cho ý kiến chỉ đạo (bút phê), phân công phòng chủ trì
            ─► TRƯỞNG PHÒNG giao công chức ─► CÔNG CHỨC xử lý, cập nhật tiến độ, dự thảo văn bản trả lời
            ─► trình ─► "Chờ trưởng phòng kiểm tra" ─► TRƯỞNG PHÒNG kiểm tra nội dung, thể thức (hoặc trả về)
            ─► "Chờ lãnh đạo ký" ─► LÃNH ĐẠO ký duyệt (hoặc trả về xử lý)
            ─► "Chờ văn thư phát hành" ─► VĂN THƯ cấp SỐ ĐI + ngày ban hành, đăng ký sổ văn bản đi, phát hành
            ─► cơ quan giao nhận báo cáo ─► kiểm tra: XÁC NHẬN hoàn thành hoặc TRẢ LẠI yêu cầu bổ sung
```

- Số/ký hiệu văn bản báo cáo **do hệ thống cấp** khi phát hành (`{số đi}/BC-{viết tắt}`), số đi tăng liên tiếp theo đơn vị và năm – người ký không tự nhập.
- Đơn vị không có trưởng phòng (trường học) thì dự thảo chuyển thẳng lên người ký; người ký kiêm văn thư (hiệu trưởng, lãnh đạo cơ quan) thì ký xong hệ thống cấp số, phát hành luôn.
- Sổ văn bản đến / đi xem và xuất Excel tại mục **Sổ văn bản đến / đi** (`GET /api/tasks/registers/{den|di}`).

#### Quy trình đánh giá mức độ chuyển đổi số theo kỳ

```
Kỳ mở ─► CÔNG CHỨC / GIÁO VIÊN lập phiếu: khai giá trị tiêu chí khảo sát + minh chứng (gợi ý sẵn số liệu kỳ trước)
      ─► LÃNH ĐẠO đơn vị duyệt, nộp (bắt buộc khai đủ tiêu chí, có minh chứng ≥ 1/2 số tiêu chí)
      ─► CƠ QUAN THẨM ĐỊNH (Sở KH&CN: cơ quan hành chính; Sở GD&ĐT: trường học) đối chiếu minh chứng,
         chấp nhận / điều chỉnh từng tiêu chí ─► phê duyệt  hoặc  trả lại yêu cầu giải trình (đơn vị sửa, nộp lại)
      ─► phê duyệt: số liệu sau thẩm định ghi thành lô Bronze "tu_danh_gia" → Silver → Gold, tính lại DTI (tạm tính)
      ─► LÃNH ĐẠO UBND TỈNH công bố bằng quyết định (khi không còn phiếu chờ thẩm định) ─► kết quả CHÍNH THỨC, khóa số liệu kỳ
```

Các tiêu chí nguồn tự động (tỷ lệ hoàn thành nhiệm vụ đúng hạn, hạ tầng, dịch vụ số) không nằm trong phiếu vì
hệ thống tự tính từ dữ liệu vận hành. Tổng quan CĐS gắn nhãn *Kết quả chính thức · QĐ …* hoặc *Tạm tính*.

Mỗi thao tác ở backend kiểm tra 3 điều: (1) vai trò có quyền của thao tác đó, (2) người dùng thuộc đúng đơn vị
(phía nhận) hoặc là cơ quan giao / cấp tỉnh (phía xác nhận), (3) trạng thái hiện tại cho phép thao tác.

### Phân cấp quản trị

| | Quản trị hệ thống (tỉnh) | Quản trị cấp xã/phường |
|---|---|---|
| Thấy tài khoản | Toàn tỉnh | Chỉ người thuộc UBND xã + các trường trên địa bàn |
| Gán được vai trò | Tất cả | Chỉ vai trò cấp xã & trường, không gán vai trò có quyền quản trị |
| Tạo/sửa vai trò, ma trận quyền | ✓ | ✗ |
| Khóa/mở, cấp lại mật khẩu tạm | ✓ | ✓ (trong phạm vi) |
| Nhật ký hoạt động | Toàn hệ thống | Người trong địa bàn |

Form cấp tài khoản theo 3 bước **Cấp → Chức danh → Đơn vị**; đơn vị được lọc theo cấp (vai trò cấp trường chỉ chọn được
trường học, cấp xã chỉ chọn UBND xã) và backend kiểm tra lại.

### Bàn làm việc theo chức danh (trang chủ của mọi người dùng)

| Vai trò | Hàng đợi công việc |
|---|---|
| Văn thư | Văn bản đến chờ tiếp nhận |
| Lãnh đạo xã | Chờ phân công · Chờ duyệt & ký · Báo cáo của trường chờ xác nhận · Cấp dưới quá hạn |
| Trưởng phòng | Chờ phân công · Việc đang xử lý · Bị trả lại |
| Công chức / giáo viên | Việc đang xử lý · Bị trả lại |
| Hiệu trưởng | Chờ tiếp nhận · Chờ phân công · Chờ duyệt & ký |
| Lãnh đạo tỉnh / VP UBND tỉnh | Báo cáo chờ xác nhận · Đơn vị quá hạn |
| Chuyên viên dữ liệu, AM, Quản trị | Lối tắt tới chức năng riêng (nhập dữ liệu / AM / quản trị tài khoản) |

Menu cũng chỉ hiện chức năng thuộc quyền: văn thư chỉ có *Bàn làm việc* và *Văn bản & nhiệm vụ*; quản trị xã chỉ có
*Bàn làm việc*, *Đơn vị*, *Quản trị*; công chức không có dashboard/hoạch định.

### Nguyên tắc "cần biết" (need-to-know)

- Ma trận vai trò, danh sách mọi vai trò/tài khoản, cấu hình bộ tiêu chí, pipeline dữ liệu, mô hình ML là **thông tin hệ thống**:
  chỉ quản trị / chuyên viên dữ liệu thấy (API trả 401/403 với người khác, giao diện ẩn menu và chặn đường dẫn).
- Mỗi người dùng chỉ có trang **Tài khoản của tôi**: vai trò, phạm vi, việc phụ trách, quyền của chính mình, đổi mật khẩu.
- Trang đăng nhập chỉ hiện tài khoản thử nghiệm khi `DEMO_MODE=true` (tắt khi triển khai thật).

### Tách biệt nhiệm vụ: quản trị ≠ nghiệp vụ

Quản trị hệ thống chỉ có quyền `user.manage`, `role.manage`, `audit.view`, `catalog.manage`: cấp/khóa tài khoản, phân quyền,
danh mục đơn vị (thông tin hành chính, **không có điểm DTI**), nhật ký. Admin **không** xem dashboard, xếp hạng, cảnh báo,
hoạch định, AM, dữ liệu khảo sát, bộ tiêu chí và **không** xử lý văn bản. Bàn làm việc của admin là bảng tình hình vận hành
(tài khoản, đăng nhập, hoạt động gần đây). Khi cần hỗ trợ người dùng, admin dùng "Xem dưới vai trò" (chỉ xem, có ghi nhật ký).

### Chức năng của Quản trị hệ thống (8 nhóm)

| Nhóm | Chức năng | Ghi chú kỹ thuật |
|---|---|---|
| 1. Bảo mật tài khoản | Chính sách mật khẩu (độ dài, độ phức tạp, hết hạn); bắt đổi mật khẩu ở lần đầu / sau khi cấp mật khẩu tạm; khóa tạm sau N lần sai, mở khóa; xem phiên đăng nhập (thiết bị, IP, trực tuyến) và buộc đăng xuất | Bảng `user_sessions`: JWT mang `jti`, mỗi request kiểm tra phiên chưa bị thu hồi; đổi mật khẩu / khóa tài khoản → thu hồi phiên |
| 2. Nhập / xuất hàng loạt | File mẫu Excel (kèm sheet mã vai trò, mã đơn vị trong phạm vi) → **Kiểm tra** (không ghi) → **Tạo**, sinh mật khẩu tạm; xuất danh sách tài khoản; tài khoản không hoạt động > N ngày → khóa hàng loạt | Dùng lại đúng hàm kiểm tra phân cấp của form cấp tài khoản |
| 3. Chuyển giao | Cán bộ nghỉ / chuyển công tác: chuyển việc đang xử lý & đơn vị AM sang người thay thế, ghi lịch sử, tùy chọn khóa tài khoản | Ghi `task_logs`, thông báo người nhận |
| 4. Cấu hình | Tham số hệ thống (bảng `system_settings`); kỳ đánh giá: tạo kỳ, đặt kỳ hiện hành, **khóa số liệu** (pipeline từ chối, không tính lại); danh mục đơn vị & địa bàn | |
| 5. Thông báo hệ thống | Gửi thông báo bảo trì/hướng dẫn tới tất cả hoặc theo cấp, mức Thông tin / Lưu ý / Khẩn | Dùng chung chuông thông báo |
| 6. Giám sát & sao lưu | Thời gian chạy, dung lượng CSDL, số bản ghi từng schema, phiên hoạt động, lỗi máy chủ (middleware ghi `api_errors`); sao lưu `pg_dump` (custom), tải về, xóa | Phục hồi: `pg_restore -c -d dti_platform tệp.dump` |
| 7. Nhật ký nâng cao | Lọc theo người dùng, hành động, khoảng ngày; xuất Excel; cảnh báo bảo mật: sai mật khẩu nhiều lần, tài khoản đang khóa, đăng nhập ngoài giờ, xem dưới vai trò, đổi cấu hình, sao lưu/tải CSDL | |
| 8. Tích hợp API | Cấp/thu hồi khóa API (chỉ lưu SHA-256, hiển thị khóa gốc 1 lần), phạm vi `dti.read`, `units.read`, `metrics.push`, hạn dùng, thống kê sử dụng | `GET /api/integration/dti`, `GET /api/integration/units`, `POST /api/integration/metrics` (đi qua pipeline Bronze→Gold) |

Quản trị cấp xã dùng được nhóm 1, 2, 3, 7 trong phạm vi địa bàn; nhóm 4 (tham số, kỳ), 5, 6, 8 chỉ quản trị tỉnh.

### Quản trị "xem dưới vai trò" (impersonation)

- Chỉ **Quản trị hệ thống cấp tỉnh** có chức năng này (trang *Ma trận vai trò hệ thống* hoặc nút 👁 ở danh sách tài khoản).
- Hệ thống cấp token phiên riêng mang dấu `imp_by` (hết hạn 2 giờ): giao diện, menu, dữ liệu, bàn làm việc hiển thị đúng như
  người dùng đó; thanh màu cam luôn báo đang xem thử, nút **Trở về quản trị** cấp lại token quản trị.
- **Chế độ chỉ xem**: middleware chặn mọi request ghi (POST/PUT/DELETE) khi token có `imp_by`, tránh quản trị thao tác thay người dùng.
- Ghi nhật ký `impersonate_start` / `impersonate_stop`. Người dùng thường không có chức năng này.

### Các chức năng liên thông bổ sung

| Chức năng | Mô tả |
|---|---|
| Số đến | Văn thư tiếp nhận → tự cấp số đến theo sổ văn bản đến của đơn vị, theo năm |
| Thông báo / nhắc việc | Mỗi bước tự báo cho người làm bước kế tiếp (văn thư → lãnh đạo → công chức → lãnh đạo ký → cơ quan giao); chuông trên thanh tiêu đề, bấm mở thẳng nhiệm vụ |
| Đôn đốc | Cơ quan giao / VP UBND tỉnh gửi nhắc việc tới đơn vị chưa báo cáo (ghi lịch sử) |
| Đính kèm | Cơ quan giao đính kèm văn bản giao; đơn vị nhận đính kèm báo cáo (PDF, Word, Excel, ảnh, ZIP ≤ 20MB) |
| Tự khai báo hạ tầng | Đơn vị (quyền `unit.self_update`) cập nhật hạ tầng CNTT của chính mình → đồng bộ vào DTI |
| Phân công AM | Quản trị tỉnh chọn đơn vị phụ trách cho nhân viên AM (thêm nhanh theo xã/phường) |

`scoped_unit_ids()` trả về danh sách đơn vị được phép, mọi truy vấn phân tích đều thêm `WHERE unit_id IN (...)`.
Riêng nghiệp vụ nhiệm vụ còn kiểm tra **chính chủ**: chỉ đơn vị được giao mới tiếp nhận/báo cáo (lãnh đạo phường
xem được trường học nhưng không tiếp nhận thay), chỉ cơ quan giao (hoặc cấp tỉnh) mới xác nhận/trả lại.
Ma trận quyền chỉnh trực tiếp ở *Quản trị → Vai trò & phân quyền*; mọi thao tác ghi `audit_logs`.

## 5. Pipeline dữ liệu Bronze – Silver – Gold

```
Nguồn ──► BRONZE ──────────────► SILVER ─────────────────────► GOLD ─────────────► Phân tích
 • File CSV/Excel khảo sát     • Ánh xạ mã đơn vị           • Điểm tiêu chí             • Dashboard
   (bảng rộng hoặc dạng dài)   • Chuẩn hóa kỳ: "Quý 3/2026",• Điểm trụ cột              • Xếp hạng
 • Dữ liệu vận hành:             "Q3-2026" → 2026-Q3        • DTI + mức độ + hạng       • Cảnh báo
   nhiệm vụ, hạ tầng,          • Ép kiểu: "85%", "0,85",    • So sánh kỳ trước          • Hoạch định
   dịch vụ số                    "Có/x/không" → số          • Tổng hợp xã/phường        • Báo cáo Excel
 Lưu nguyên trạng JSONB        • Kiểm tra miền [0,100], ≥0  • Cảnh báo, chỉ số ưu tiên
 + thông tin lô nhập           • Loại trùng (dòng sau thắng)• Đề xuất giải pháp
                               • Lỗi → rejected_records     • K-Means + dự báo
                                 (dòng, cột, giá trị, lý do)
```

- **Upload** (`POST /api/data/upload`) chạy trọn chuỗi; mỗi lô xem lại được dữ liệu thô và danh sách lỗi.
- **Đồng bộ vận hành** (`POST /api/data/sync`) tự sinh chỉ số không cần nhập tay:
  HD03 (tỷ lệ nhiệm vụ đúng hạn – từ module nhiệm vụ), HT02/AT02/AT03 (từ hồ sơ hạ tầng), DV06 (mức khai thác dịch vụ).
- Silver dùng `INSERT … ON CONFLICT DO UPDATE` → nạp lại dữ liệu là cập nhật, không nhân bản.

## 6. Phương pháp xây dựng chỉ số DTI

**7 trụ cột (trọng số):** Nhận thức số 10 · Thể chế số 10 · Hạ tầng số 15 · Nhân lực số 15 · An toàn thông tin 15 ·
Hoạt động điều hành số 20 · Dịch vụ số & CĐS chuyên ngành 15. 24 tiêu chí, có tiêu chí riêng cho hành chính
(DVC trực tuyến toàn trình, mạng TSLCD…) và giáo dục (học bạ số, LMS, phòng học thông minh).

1. Điểm tiêu chí `s = min(giá_trị / mục_tiêu, 1) × 100`; tiêu chí Có/Không: 0 hoặc 100.
2. Điểm trụ cột = Σ(s × trọng số tiêu chí) / Σ trọng số (chỉ các tiêu chí áp dụng cho loại hình).
3. **DTI = Σ(điểm trụ cột × trọng số trụ cột) / Σ trọng số trụ cột** (0–100).
4. Phân loại: < 30 Khởi đầu · 30–50 Cơ bản · 50–70 Phát triển · 70–85 Nâng cao · ≥ 85 Dẫn đầu.
5. Xếp hạng toàn tỉnh & trong cùng loại hình; Δ so với kỳ trước; độ đầy đủ dữ liệu.

Quy ước: thiếu dữ liệu khảo sát = 0 điểm (khuyến khích báo cáo đầy đủ); tiêu chí lấy từ nhiệm vụ chỉ tính khi đơn vị
có nhiệm vụ đến hạn trong kỳ (không phạt đơn vị không được giao việc). Trọng số/mục tiêu chỉnh trên giao diện rồi bấm
*Áp dụng & tính lại DTI* (tính lại toàn bộ các kỳ).

## 7. Cảnh báo & xác định đơn vị ưu tiên

| Loại | Điều kiện | Mức |
|---|---|---|
| LOW_SCORE | DTI < 40 | cao nếu < 30 |
| SCORE_DROP | giảm ≥ 5 điểm so kỳ trước | cao nếu ≥ 10 |
| WEAK_PILLAR | trụ cột < 30 | trung bình |
| OVERDUE_TASK | nhiệm vụ quá hạn / hoàn thành trễ | cao nếu ≥ 2 |
| MISSING_DATA | độ đầy đủ < 80% | thấp |
| EXPIRING_SERVICE | dịch vụ hết hạn ≤ 60 ngày | thấp |

**Chỉ số ưu tiên (0–100)** = 0,55·(100 − DTI) + 0,15·min(5·mức giảm, 100) + 0,15·tỷ lệ nhiệm vụ trễ + 0,15·tỷ lệ trụ cột yếu.

## 8. Hỗ trợ hoạch định (đề xuất nhóm giải pháp)

Luật: mỗi nhóm giải pháp có danh sách **tiêu chí kích hoạt**. Nếu điểm trung bình các tiêu chí đó của đơn vị ≤ 60
→ đề xuất; **điểm ưu tiên** = (100 − điểm TB) × (0,6 + 0,4 × trọng số trụ cột / 20); ≥ 70 cao, ≥ 50 trung bình.
Mỗi đề xuất ghi rõ **căn cứ** (2 tiêu chí yếu nhất), **hành động**, thời gian, mức chi phí và **dịch vụ còn thiếu**.
Màn hình Hoạch định gộp theo phạm vi: nhóm giải pháp nào cần cho bao nhiêu đơn vị, đơn vị nào ưu tiên trước.
Hệ thống *hỗ trợ* chứ không thay quyết định của người quản lý (đề cương 4.7).

## 9. AM Intelligence

Cho đơn vị được phân công: DTI, số dịch vụ, doanh thu/tháng, mức khai thác;
**cơ hội** = dịch vụ thuộc nhóm giải pháp được đề xuất mà đơn vị chưa dùng (ước tính giá trị);
**gia hạn** = dịch vụ hết hạn ≤ 60 ngày; **chăm sóc** = dịch vụ đang dùng nhưng khai thác < 40%; tỷ lệ phủ dịch vụ.

## 10. Machine Learning

- **K-Means** (k = 4, chuẩn hóa StandardScaler) trên vector 7 điểm trụ cột → nhóm đơn vị tương đồng; đặt tên cụm theo
  điểm trung bình tâm cụm; đánh giá bằng **silhouette score**. Dùng để hoạch định theo nhóm.
- **Hồi quy tuyến tính** DTI theo thời gian từng đơn vị (≥ 3 kỳ) → dự báo kỳ kế tiếp và độ dốc xu hướng.

## 11. Kiểm thử

`scripts/smoke_test.py` kiểm tra ~60 tình huống: đăng nhập đúng/sai; mọi endpoint; phạm vi dữ liệu (phường chỉ thấy
5 đơn vị, trường thấy 1); chặn truy cập trái phép (403); luồng nhiệm vụ đầy đủ kể cả các thao tác sai vai
(phường tiếp nhận thay trường, trường tự xác nhận, lãnh đạo kiểm tra thay trưởng phòng, trưởng phòng ký,
văn thư phát hành khi chưa ký, cấp trên xác nhận khi chưa phát hành); sổ văn bản đến/đi; upload file lỗi (mã đơn vị sai, kỳ sai,
mã tiêu chí sai, tỷ lệ 150%) và kiểm tra lý do loại.
`scripts/test_assessment.py` kiểm tra quy trình tự đánh giá → thẩm định → công bố: phân quyền từng bước, giá trị sai
bị từ chối, khóa sửa sau khi nộp, trả lại – nộp lại, phạm vi thẩm định (Sở KH&CN chỉ thấy cơ quan hành chính, Sở GD&ĐT
chỉ thấy trường), số liệu sau phê duyệt đi qua pipeline, không công bố khi còn phiếu chờ thẩm định.

### Căn cứ quy trình tham chiếu
- Nghị định 30/2020/NĐ-CP về công tác văn thư: quy trình quản lý văn bản đến (tiếp nhận – đăng ký – trình, chuyển giao –
  giải quyết, theo dõi) và văn bản đi (soạn thảo – kiểm tra – ký – cấp số, thời gian ban hành – đăng ký – phát hành – lưu).
- Bộ chỉ số đánh giá mức độ chuyển đổi số (DTI) cấp tỉnh/cơ quan: đơn vị tự đánh giá kèm tài liệu kiểm chứng, cơ quan
  chủ trì (Sở KH&CN) thẩm định, UBND tỉnh quyết định công bố kết quả.
- Quyết định 4725/QĐ-BGDĐT (Bộ chỉ số CĐS cơ sở giáo dục phổ thông): nhà trường tự đánh giá, cơ quan quản lý giáo dục đánh giá.

## 12. Hạn chế & hướng phát triển

- Chưa kết nối trực tiếp API của VBĐH tỉnh (chưa có tài liệu tích hợp) → hiện nhập/đồng bộ qua module nhiệm vụ nội bộ;
  hướng phát triển: đồng bộ qua trục LGSP của tỉnh.
- Dữ liệu thực nghiệm là mô phỏng; cần hiệu chỉnh trọng số với dữ liệu thật và ý kiến chuyên gia (AHP).
- Quy mô lớn có thể thay Pandas bằng PySpark ở bước Silver/Gold; bổ sung bản đồ GIS theo xã/phường.
