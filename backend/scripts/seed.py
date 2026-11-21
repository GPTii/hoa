"""Khởi tạo CSDL.

  python -m scripts.seed                                   → BẢN MẪU tỉnh Tây Ninh (dữ liệu mô phỏng đầy đủ để demo)
  python -m scripts.seed --blank --province "Bình Phước"   → HỆ THỐNG TRỐNG cho một tỉnh mới (chỉ có khung:
        quyền, vai trò, bộ tiêu chí, nhóm giải pháp, danh mục dịch vụ, kỳ đánh giá, tài khoản admin).
        Sau đó đăng nhập admin → Quản trị → "Thiết lập tỉnh mới" để làm tiếp từng bước.
  Tùy chọn: --type "Thành phố"  --org "Sở Khoa học và Công nghệ"  --admin-password "MatKhauManh@2026"

Cảnh báo: XÓA và tạo lại toàn bộ bảng.

Dữ liệu là MÔ PHỎNG (đề cương mục 3.2 cho phép dùng dữ liệu mô phỏng/ẩn danh), dựng theo mô hình
chính quyền 2 cấp tỉnh Tây Ninh: UBND tỉnh, Văn phòng UBND tỉnh, các Sở → UBND xã/phường → trường học.
Dữ liệu khảo sát từng kỳ được sinh thành bảng rộng (như file Excel thực tế, có cố ý chèn lỗi định dạng)
rồi đưa qua ĐÚNG pipeline Bronze → Silver → Gold của hệ thống.
"""
import io
import math
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.db import Base, SessionLocal, engine, init_schemas  # noqa: E402
from app.models import (  # noqa: E402
    AMAssignment, Criterion, Period, Permission, Pillar, Region, Role, ServiceCatalog, SolutionGroup, Task,
    TaskAssignment, TaskLog, Unit, UnitInfra, UnitService, User,
)
from app.security import hash_password  # noqa: E402
from app.services import ml, pipeline, scoring  # noqa: E402

random.seed(2026)
np.random.seed(2026)
TODAY = date.today()
SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"

# ----------------------------------------------------------------- danh mục tĩnh

PERMISSIONS = [
    ("dashboard.view", "Xem dashboard tổng quan", "Dashboard"),
    ("unit.view", "Xem thông tin đơn vị", "Đơn vị"),
    ("unit.manage", "Quản lý đơn vị, hạ tầng, dịch vụ", "Đơn vị"),
    ("unit.self_update", "Tự khai báo hạ tầng CNTT của đơn vị mình", "Đơn vị"),
    ("catalog.manage", "Quản lý danh mục đơn vị, địa bàn (thông tin hành chính)", "Quản trị"),
    ("data.view", "Xem dữ liệu & lô nhập", "Dữ liệu"),
    ("data.import", "Nhập & xử lý dữ liệu (pipeline)", "Dữ liệu"),
    ("score.compute", "Tính toán lại chỉ số DTI", "Đánh giá"),
    ("criteria.manage", "Quản lý bộ tiêu chí, trọng số", "Đánh giá"),
    ("alert.view", "Xem cảnh báo & đơn vị ưu tiên", "Đánh giá"),
    ("plan.view", "Xem đề xuất & hỗ trợ hoạch định", "Hoạch định"),
    ("plan.manage", "Lập, ban hành kế hoạch cải thiện CĐS", "Hoạch định"),
    ("ml.run", "Chạy mô hình phân cụm/dự báo", "Phân tích"),
    ("task.view", "Xem nhiệm vụ của đơn vị", "Nhiệm vụ"),
    ("task.assign", "Giao nhiệm vụ / giao tiếp cho cấp dưới", "Nhiệm vụ"),
    ("task.confirm", "Kiểm tra, xác nhận hoặc trả lại kết quả cấp dưới", "Nhiệm vụ"),
    ("task.receive", "Tiếp nhận / không tiếp nhận văn bản đến (văn thư)", "Nhiệm vụ"),
    ("task.dispatch", "Phân công phòng, công chức xử lý", "Nhiệm vụ"),
    ("task.process", "Xử lý, cập nhật tiến độ, trình dự thảo báo cáo", "Nhiệm vụ"),
    ("task.review", "Kiểm tra dự thảo của công chức trước khi trình ký", "Nhiệm vụ"),
    ("task.sign", "Ký duyệt văn bản báo cáo (ký số)", "Nhiệm vụ"),
    ("task.issue", "Cấp số, đăng ký sổ văn bản đi & phát hành (văn thư)", "Nhiệm vụ"),
    ("assess.prepare", "Lập phiếu tự đánh giá CĐS của đơn vị (khai số liệu, minh chứng)", "Đánh giá"),
    ("assess.submit", "Duyệt, nộp phiếu tự đánh giá của đơn vị", "Đánh giá"),
    ("assess.review", "Thẩm định phiếu tự đánh giá của đơn vị", "Đánh giá"),
    ("assess.publish", "Công bố kết quả đánh giá chính thức của kỳ", "Đánh giá"),
    ("am.view", "AM Intelligence", "AM"),
    ("report.view", "Xem báo cáo", "Báo cáo"),
    ("report.export", "Xuất báo cáo Excel", "Báo cáo"),
    ("user.manage", "Quản lý người dùng", "Quản trị"),
    ("role.manage", "Quản lý vai trò & phân quyền", "Quản trị"),
    ("audit.view", "Theo dõi nhật ký hệ thống", "Quản trị"),
]
ALL = [p[0] for p in PERMISSIONS]
VIEW = ["dashboard.view", "unit.view", "alert.view", "plan.view", "report.view"]
# code, tên, mô tả, phạm vi dữ liệu, cấp, công việc chính ('|'), quyền
ROLES = [
    ("admin", "Quản trị hệ thống", "Trung tâm CĐS – vận hành nền tảng (tách biệt với nghiệp vụ: không xem số liệu, không xử lý văn bản)", "all", "he_thong",
     "Cấp, khóa tài khoản; phân quyền vai trò|Quản lý danh mục đơn vị, địa bàn|Theo dõi nhật ký hệ thống|Xem dưới vai trò người dùng để hỗ trợ (chỉ xem)",
     ["user.manage", "role.manage", "audit.view", "catalog.manage"]),
    # ---- cấp tỉnh
    ("lanh_dao_tinh", "Lãnh đạo UBND tỉnh", "Chủ tịch, Phó Chủ tịch UBND tỉnh", "all", "tinh",
     "Xem bức tranh CĐS toàn tỉnh, xếp hạng xã/phường|Giao nhiệm vụ cho Sở, UBND xã/phường|Xác nhận kết quả báo cáo|Công bố kết quả đánh giá CĐS chính thức của kỳ (quyết định)|Xem đề xuất, phân cụm để ra quyết định",
     VIEW + ["ml.run", "task.view", "task.assign", "task.confirm", "report.export", "plan.manage", "assess.publish"]),
    ("vp_ubnd_tinh", "Chuyên viên Văn phòng UBND tỉnh", "Tiếp nhận – tham mưu – theo dõi – đôn đốc nhiệm vụ (QĐ 38/2026)", "all", "tinh",
     "Theo dõi tiến độ mọi nhiệm vụ UBND tỉnh giao|Đôn đốc, xác nhận hoặc trả lại báo cáo của xã/phường|Tổng hợp báo cáo giao ban",
     ["dashboard.view", "unit.view", "alert.view", "report.view", "report.export", "task.view", "task.confirm"]),
    # ---- sở, ngành
    ("chuyen_vien_du_lieu", "Chuyên viên dữ liệu Sở KH&CN", "Cơ quan chủ trì chuyển đổi số – vận hành dữ liệu & bộ tiêu chí", "all", "so",
     "Thẩm định phiếu tự đánh giá của cơ quan, xã/phường (chấp nhận, điều chỉnh, yêu cầu giải trình)|Nhập, làm sạch dữ liệu khảo sát (Bronze→Silver→Gold)|Cấu hình bộ tiêu chí, trọng số DTI|Tính lại chỉ số, chạy mô hình ML|Cập nhật thông tin đơn vị, hạ tầng",
     VIEW + ["unit.manage", "data.view", "data.import", "score.compute", "criteria.manage", "ml.run", "task.view", "report.export", "assess.review"]),
    ("lanh_dao_so_gd", "Lãnh đạo Sở GD&ĐT", "Quản lý chuyên ngành giáo dục toàn tỉnh", "giao_duc", "so",
     "Theo dõi CĐS của toàn bộ trường học|Thẩm định phiếu tự đánh giá CĐS của cơ sở giáo dục|Giao nhiệm vụ chuyên môn trực tiếp cho trường (nhất là THPT)|Xác nhận báo cáo của trường",
     VIEW + ["task.view", "task.assign", "task.confirm", "report.export", "plan.manage", "assess.review"]),
    ("lanh_dao_co_quan", "Lãnh đạo cơ quan cấp tỉnh", "Giám đốc/Phó Giám đốc Sở, Thủ trưởng ban, ngành (cơ quan hành chính cấp tỉnh)", "unit", "so",
     "Theo dõi thông tin, hạ tầng, dịch vụ số, chỉ số CĐS của cơ quan|Lập và nộp phiếu tự đánh giá CĐS của cơ quan|Xem đề xuất cải thiện, lập kế hoạch cải thiện của cơ quan|Tiếp nhận, phân công, ký và phát hành báo cáo nhiệm vụ UBND tỉnh giao",
     VIEW + ["task.view", "task.receive", "task.dispatch", "task.process", "task.sign", "task.issue", "unit.self_update", "plan.manage",
             "assess.prepare", "assess.submit"]),
    # ---- cấp xã, phường
    ("lanh_dao_xa", "Lãnh đạo UBND xã/phường", "Chủ tịch, Phó Chủ tịch UBND xã, phường", "region", "xa",
     "Cho ý kiến chỉ đạo, phân công phòng chuyên môn xử lý văn bản của tỉnh|Giao tiếp nhiệm vụ cho trường trên địa bàn|Xác nhận kết quả của trường|Ký duyệt báo cáo gửi tỉnh (văn thư cấp số, phát hành)|Duyệt, nộp phiếu tự đánh giá CĐS của xã/phường",
     VIEW + ["task.view", "task.assign", "task.confirm", "task.dispatch", "task.sign", "report.export", "unit.self_update", "plan.manage",
             "assess.submit"]),
    ("van_thu_xa", "Văn thư UBND xã/phường", "Văn phòng HĐND và UBND – tiếp nhận, vào sổ văn bản", "unit", "xa",
     "Tiếp nhận, đăng ký sổ văn bản đến (hoặc không tiếp nhận kèm lý do)|Trình lãnh đạo cho ý kiến chỉ đạo|Cấp số, ngày, đăng ký sổ văn bản đi và phát hành văn bản đã ký|Quản lý sổ văn bản đến / đi",
     ["task.view", "task.receive", "task.issue"]),
    ("truong_phong_xa", "Trưởng phòng chuyên môn xã", "Lãnh đạo Phòng Văn hóa – Xã hội / Phòng Kinh tế", "region", "xa",
     "Phân công công chức trong phòng|Theo dõi, cập nhật tiến độ|Kiểm tra nội dung, thể thức dự thảo trước khi trình lãnh đạo ký (hoặc trả về)",
     ["dashboard.view", "unit.view", "task.view", "task.dispatch", "task.process", "task.review"]),
    ("cong_chuc_xa", "Công chức chuyên môn xã", "Công chức được giao xử lý (VD phụ trách CĐS)", "region", "xa",
     "Xử lý nội dung được giao, cập nhật tiến độ|Tổng hợp số liệu các trường|Dự thảo báo cáo, trình trưởng phòng kiểm tra|Lập phiếu tự đánh giá CĐS của xã/phường kèm minh chứng",
     ["unit.view", "task.view", "task.process", "unit.self_update", "assess.prepare"]),
    ("quan_tri_xa", "Quản trị hệ thống cấp xã/phường", "Cán bộ được giao quản trị tài khoản của xã và các trường trên địa bàn", "region", "xa",
     "Cấp, khóa, cấp lại mật khẩu tài khoản cán bộ xã và trường học|Gán vai trò cấp xã / trường (không gán được vai trò cấp tỉnh)|Xem nhật ký hoạt động trong địa bàn",
     ["unit.view", "user.manage", "audit.view"]),
    # ---- cơ sở giáo dục
    ("hieu_truong", "Hiệu trưởng", "Lãnh đạo trường mầm non, tiểu học, THCS, THPT", "unit", "truong",
     "Tiếp nhận nhiệm vụ của xã/Sở (kiêm văn thư trường)|Phân công giáo viên phụ trách|Ký duyệt, phát hành báo cáo gửi lên|Chủ trì tự đánh giá CĐS của trường, duyệt nộp phiếu|Xem đề xuất cải thiện CĐS của trường",
     ["dashboard.view", "unit.view", "alert.view", "plan.view", "task.view", "task.receive", "task.dispatch", "task.sign", "task.issue",
      "unit.self_update", "plan.manage", "assess.submit"]),
    ("can_bo_truong", "Giáo viên / cán bộ phụ trách CNTT", "Người được hiệu trưởng phân công xử lý", "unit", "truong",
     "Cập nhật số liệu, tiến độ|Dự thảo báo cáo, trình hiệu trưởng|Khai báo hạ tầng CNTT của trường|Khai phiếu tự đánh giá CĐS của trường kèm minh chứng",
     ["unit.view", "task.view", "task.process", "unit.self_update", "assess.prepare"]),
    # ---- đối tác
    ("am", "Nhân viên phụ trách (AM)", "Doanh nghiệp viễn thông – CNTT chăm sóc đơn vị", "assigned", "khac",
     "Theo dõi đơn vị được phân công|Phát hiện cơ hội dịch vụ, gia hạn|Lập kế hoạch chăm sóc",
     ["dashboard.view", "unit.view", "alert.view", "plan.view", "am.view", "report.view", "report.export"]),
]

PILLARS = [
    ("NT", "Nhận thức số", "Mức độ quan tâm, chỉ đạo, tuyên truyền về chuyển đổi số", 10),
    ("TC", "Thể chế số", "Quy chế, kế hoạch, nguồn lực tài chính cho chuyển đổi số", 10),
    ("HT", "Hạ tầng số", "Thiết bị, đường truyền, kết nối mạng, phòng học thông minh", 15),
    ("NL", "Nhân lực số", "Cán bộ chuyên trách, kỹ năng số, chữ ký số cá nhân", 15),
    ("AT", "An toàn thông tin", "Phê duyệt cấp độ, giải pháp bảo vệ, sao lưu dữ liệu", 15),
    ("HD", "Hoạt động điều hành số", "Văn bản điện tử, hồ sơ công việc, nhiệm vụ đúng hạn, họp trực tuyến", 20),
    ("DV", "Dịch vụ số & CĐS chuyên ngành", "Dịch vụ công trực tuyến, học bạ số, học trực tuyến, thanh toán số", 15),
]
# code, pillar, name, unit_type, metric, target, weight, unit_label, source, độ khó (offset)
CRITERIA = [
    ("NT01", "NT", "Có Ban chỉ đạo/Tổ công tác CĐS và kế hoạch CĐS năm", "all", "boolean", 1, 2, None, "survey", 0.15),
    ("NT02", "NT", "Tỷ lệ CBCCVC/giáo viên được tuyên truyền, phổ biến về CĐS", "all", "ratio", 100, 1, "%", "survey", 0.1),
    ("TC01", "TC", "Ban hành quy chế quản lý, vận hành hệ thống thông tin", "all", "boolean", 1, 1, None, "survey", 0.0),
    ("TC02", "TC", "Tỷ lệ kinh phí CĐS trên tổng chi thường xuyên", "all", "number", 3, 1, "%", "survey", -0.1),
    ("HT01", "HT", "Tỷ lệ cán bộ/giáo viên có máy tính phục vụ công việc", "all", "ratio", 100, 2, "%", "survey", 0.2),
    ("HT02", "HT", "Băng thông Internet của đơn vị", "all", "number", 300, 1, "Mbps", "infra", 0.0),
    ("HT03", "HT", "Tỷ lệ phòng học thông minh/phòng học", "giao_duc", "ratio", 50, 1, "%", "survey", -0.15),
    ("HT04", "HT", "Kết nối Mạng truyền số liệu chuyên dùng", "hanh_chinh", "boolean", 1, 1, None, "survey", 0.1),
    ("NL01", "NL", "Có cán bộ chuyên trách/phụ trách CNTT", "all", "boolean", 1, 1, None, "survey", 0.05),
    ("NL02", "NL", "Tỷ lệ CBCC/giáo viên được đào tạo kỹ năng số", "all", "ratio", 100, 2, "%", "survey", 0.0),
    ("NL03", "NL", "Tỷ lệ cán bộ có chữ ký số cá nhân", "all", "ratio", 100, 1, "%", "survey", 0.05),
    ("AT01", "AT", "Tỷ lệ hệ thống thông tin được phê duyệt cấp độ ATTT", "all", "ratio", 100, 1, "%", "survey", -0.2),
    ("AT02", "AT", "Có tường lửa, phòng chống mã độc tập trung", "all", "boolean", 1, 1, None, "infra", -0.05),
    ("AT03", "AT", "Có sao lưu dữ liệu định kỳ", "all", "boolean", 1, 1, None, "infra", -0.1),
    ("HD01", "HD", "Tỷ lệ văn bản đi được ký số, gửi nhận qua hệ thống VBĐH", "all", "ratio", 100, 2, "%", "survey", 0.2),
    ("HD02", "HD", "Tỷ lệ hồ sơ công việc xử lý trên môi trường mạng", "all", "ratio", 100, 1, "%", "survey", 0.0),
    ("HD03", "HD", "Tỷ lệ nhiệm vụ được giao hoàn thành đúng hạn", "all", "ratio", 100, 2, "%", "tasks", 0.0),
    ("HD04", "HD", "Tỷ lệ cuộc họp trực tuyến, không giấy", "all", "ratio", 100, 1, "%", "survey", -0.05),
    ("DV01", "DV", "Tỷ lệ hồ sơ TTHC xử lý trực tuyến toàn trình", "hanh_chinh", "ratio", 100, 2, "%", "survey", -0.05),
    ("DV02", "DV", "Tỷ lệ số hóa kết quả giải quyết TTHC", "hanh_chinh", "ratio", 100, 1, "%", "survey", 0.0),
    ("DV03", "DV", "Tỷ lệ giao dịch thanh toán không dùng tiền mặt (phí, lệ phí, học phí)", "all", "ratio", 100, 1, "%", "survey", -0.05),
    ("DV04", "DV", "Áp dụng học bạ số, sổ điểm điện tử", "giao_duc", "boolean", 1, 2, None, "survey", 0.05),
    ("DV05", "DV", "Tỷ lệ học sinh có tài khoản học tập trực tuyến (LMS)", "giao_duc", "ratio", 100, 1, "%", "survey", -0.05),
    ("DV06", "DV", "Mức độ khai thác các dịch vụ số đang sử dụng", "all", "ratio", 100, 1, "%", "services", 0.0),
]
# code, name, category, pillar, unit_types, price, desc
SERVICES = [
    ("VBDH", "Hệ thống Quản lý văn bản và điều hành (VNPT iOffice)", "dieu_hanh", "HD", ["hanh_chinh", "giao_duc"], 1500000, "Văn bản điện tử, liên thông, hồ sơ công việc"),
    ("SMARTCA", "Chữ ký số cá nhân VNPT SmartCA", "ky_so", "NL", ["hanh_chinh", "giao_duc"], 400000, "Ký số văn bản, hồ sơ trên di động"),
    ("IGATE", "Hệ thống thông tin giải quyết TTHC (VNPT iGate)", "dvc", "DV", ["hanh_chinh"], 3000000, "Một cửa điện tử, DVC trực tuyến toàn trình"),
    ("MEETING", "Hội nghị truyền hình trực tuyến (VNPT Meeting)", "dieu_hanh", "HD", ["hanh_chinh", "giao_duc"], 800000, "Họp trực tuyến, phòng họp không giấy"),
    ("CLOUD", "Lưu trữ & sao lưu đám mây (VNPT Cloud Backup)", "attt", "AT", ["hanh_chinh", "giao_duc"], 900000, "Sao lưu dữ liệu định kỳ, phục hồi thảm họa"),
    ("SOC", "Giám sát an toàn thông tin (VNPT SOC)", "attt", "AT", ["hanh_chinh"], 2500000, "Giám sát, cảnh báo tấn công 24/7"),
    ("FIREWALL", "Tường lửa & Internet an toàn (VNPT Clean Pipe)", "attt", "AT", ["hanh_chinh", "giao_duc"], 700000, "Chống mã độc, lọc truy cập"),
    ("FIBER", "Internet cáp quang doanh nghiệp (FiberVNN)", "ha_tang", "HT", ["hanh_chinh", "giao_duc"], 600000, "Đường truyền tốc độ cao"),
    ("TSLCD", "Mạng truyền số liệu chuyên dùng", "ha_tang", "HT", ["hanh_chinh"], 500000, "Kết nối an toàn cơ quan Đảng, Nhà nước"),
    ("WIFI", "Wifi Mesh trường học", "ha_tang", "HT", ["giao_duc"], 450000, "Phủ sóng wifi lớp học"),
    ("SMARTCLASS", "Phòng học thông minh (VNPT Smart Class)", "giao_duc", "HT", ["giao_duc"], 2000000, "Màn hình tương tác, thiết bị lớp học số"),
    ("VNEDU", "Quản lý trường học & sổ liên lạc điện tử (vnEdu)", "giao_duc", "DV", ["giao_duc"], 1000000, "Quản lý học sinh, điểm, liên lạc phụ huynh"),
    ("HOCBA", "Học bạ số (vnEdu Học bạ số)", "giao_duc", "DV", ["giao_duc"], 600000, "Học bạ điện tử có ký số"),
    ("LMS", "Học tập trực tuyến (VNPT E-Learning / LMS)", "giao_duc", "DV", ["giao_duc"], 900000, "Lớp học trực tuyến, kho học liệu số"),
    ("SMARTPAY", "Thanh toán không tiền mặt (VNPT Money/SmartPay)", "dvc", "DV", ["hanh_chinh", "giao_duc"], 0, "Thu phí, lệ phí, học phí không tiền mặt"),
    ("EINVOICE", "Hóa đơn, biên lai điện tử (VNPT Invoice)", "dvc", "TC", ["hanh_chinh", "giao_duc"], 300000, "Biên lai thu phí điện tử"),
    ("DAOTAO", "Đào tạo kỹ năng số cho CBCCVC", "dao_tao", "NL", ["hanh_chinh", "giao_duc"], 1200000, "Bồi dưỡng kỹ năng số, ATTT"),
    ("CAMERA", "Camera AI giám sát an ninh", "ha_tang", "HT", ["hanh_chinh", "giao_duc"], 700000, "Giám sát an ninh trụ sở, trường học"),
]
# code, name, pillar, triggers, unit_type, desc, actions, services, cost, months
SOLUTIONS = [
    ("GP-NT1", "Kiện toàn bộ máy chỉ đạo & truyền thông CĐS", "NT", ["NT01", "NT02"], "all",
     "Thành lập/kiện toàn Tổ công tác CĐS, ban hành kế hoạch năm, đẩy mạnh truyền thông nội bộ.",
     "Ban hành quyết định Tổ CĐS; xây dựng kế hoạch CĐS năm; tổ chức tuyên truyền hằng quý", [], "thap", 1),
    ("GP-TC1", "Hoàn thiện quy chế & bố trí nguồn lực tài chính", "TC", ["TC01", "TC02"], "all",
     "Ban hành quy chế vận hành hệ thống thông tin; ưu tiên dự toán chi cho CĐS.",
     "Ban hành quy chế; bố trí tối thiểu 1–3% chi thường xuyên cho CĐS; số hóa biên lai", ["EINVOICE"], "thap", 2),
    ("GP-HT1", "Nâng cấp thiết bị & đường truyền", "HT", ["HT01", "HT02"], "all",
     "Trang bị máy tính cho cán bộ còn thiếu; nâng cấp băng thông Internet.",
     "Rà soát, bổ sung máy tính; nâng cấp cáp quang ≥ 300 Mbps", ["FIBER"], "trung_binh", 3),
    ("GP-HT2", "Kết nối mạng truyền số liệu chuyên dùng", "HT", ["HT04"], "hanh_chinh",
     "Kết nối mạng TSLCD phục vụ liên thông văn bản, hội nghị trực tuyến an toàn.",
     "Đăng ký kết nối TSLCD cấp II; cấu hình phân vùng mạng", ["TSLCD"], "thap", 1),
    ("GP-HT3", "Xây dựng lớp học số", "HT", ["HT03"], "giao_duc",
     "Đầu tư phòng học thông minh và phủ wifi lớp học.",
     "Lộ trình phòng học thông minh theo khối lớp; triển khai wifi mesh", ["SMARTCLASS", "WIFI"], "cao", 6),
    ("GP-NL1", "Bồi dưỡng kỹ năng số & chữ ký số", "NL", ["NL02", "NL03"], "all",
     "Đào tạo kỹ năng số cơ bản – nâng cao; cấp chữ ký số cá nhân cho 100% cán bộ.",
     "Mở lớp 'Bình dân học vụ số'; cấp SmartCA cho cán bộ còn thiếu", ["DAOTAO", "SMARTCA"], "thap", 2),
    ("GP-NL2", "Bố trí cán bộ phụ trách CNTT", "NL", ["NL01"], "all",
     "Phân công cán bộ chuyên trách/kiêm nhiệm CNTT, CĐS.",
     "Quyết định phân công; cử đi bồi dưỡng chuyên sâu", [], "thap", 1),
    ("GP-AT1", "Bảo đảm an toàn thông tin theo cấp độ", "AT", ["AT01", "AT02"], "all",
     "Xây dựng hồ sơ đề xuất cấp độ; triển khai tường lửa, giám sát ATTT.",
     "Lập hồ sơ cấp độ HTTT; triển khai tường lửa; kết nối SOC", ["FIREWALL", "SOC"], "trung_binh", 3),
    ("GP-AT2", "Sao lưu & phục hồi dữ liệu", "AT", ["AT03"], "all",
     "Sao lưu dữ liệu định kỳ lên hạ tầng đám mây.",
     "Thiết lập lịch sao lưu tự động; diễn tập phục hồi 6 tháng/lần", ["CLOUD"], "thap", 1),
    ("GP-HD1", "Điều hành không giấy trên hệ thống VBĐH", "HD", ["HD01", "HD02"], "all",
     "Xử lý 100% văn bản, hồ sơ công việc trên VBĐH (trừ văn bản mật), ký số đầy đủ.",
     "Rà soát luồng xử lý; tập huấn văn thư, lãnh đạo; ký số 100% văn bản đi", ["VBDH", "SMARTCA"], "thap", 2),
    ("GP-HD2", "Nâng cao kỷ luật xử lý nhiệm vụ được giao", "HD", ["HD03"], "all",
     "Theo dõi, đôn đốc nhiệm vụ theo hạn; gắn trách nhiệm người đứng đầu.",
     "Rà soát nhiệm vụ quá hạn hằng tuần; báo cáo tại giao ban; nhắc hạn tự động", ["VBDH"], "thap", 1),
    ("GP-HD3", "Họp trực tuyến, phòng họp không giấy", "HD", ["HD04"], "all",
     "Tổ chức họp trực tuyến/không giấy để tiết kiệm thời gian, chi phí.",
     "Trang bị phòng họp trực tuyến; tài liệu họp điện tử", ["MEETING"], "trung_binh", 2),
    ("GP-DV1", "Đẩy mạnh dịch vụ công trực tuyến toàn trình", "DV", ["DV01", "DV02"], "hanh_chinh",
     "Tăng tỷ lệ hồ sơ trực tuyến toàn trình và số hóa kết quả TTHC.",
     "Hướng dẫn người dân nộp trực tuyến tại Trung tâm phục vụ HCC; số hóa kết quả", ["IGATE"], "trung_binh", 3),
    ("GP-DV2", "Thanh toán không dùng tiền mặt", "DV", ["DV03"], "all",
     "Thu phí, lệ phí, học phí qua kênh thanh toán số.",
     "Tích hợp cổng thanh toán; truyền thông người dân/phụ huynh", ["SMARTPAY"], "thap", 1),
    ("GP-DV3", "Chuyển đổi số quản trị nhà trường", "DV", ["DV04", "DV05"], "giao_duc",
     "Triển khai học bạ số, sổ điểm điện tử, nền tảng học tập trực tuyến.",
     "Triển khai học bạ số theo lộ trình Bộ GD&ĐT; tạo tài khoản LMS cho học sinh", ["VNEDU", "HOCBA", "LMS"], "trung_binh", 4),
    ("GP-DV4", "Nâng cao hiệu quả khai thác dịch vụ số", "DV", ["DV06"], "all",
     "Tập huấn, hỗ trợ sử dụng sâu các dịch vụ số đã đầu tư.",
     "Khảo sát mức sử dụng; tập huấn lại; giao chỉ tiêu khai thác", [], "thap", 1),
]

PHUONG = ["Long An", "Tân An", "Khánh Hậu", "Kiến Tường", "Tân Ninh", "Bình Minh", "Ninh Thạnh", "Long Hoa",
          "Hòa Thành", "Thanh Điền", "Trảng Bàng", "An Tịnh", "Gò Dầu", "Gia Lộc"]
XA = ["Tân Biên", "Tân Lập", "Thạnh Bình", "Tân Châu", "Tân Đông", "Tân Hòa", "Dương Minh Châu", "Truông Mít",
      "Cầu Khởi", "Châu Thành", "Hảo Đước", "Bến Cầu", "Long Chữ", "Đức Hòa", "Hậu Nghĩa", "Hòa Khánh", "Bến Lức",
      "Mỹ Yên", "Cần Giuộc", "Phước Lý", "Cần Đước", "Rạch Kiến", "Thủ Thừa", "Tân Trụ", "Đức Huệ", "Thạnh Hóa",
      "Tân Thạnh", "Mộc Hóa", "Vĩnh Hưng", "Tân Hưng"]
SO = ["Sở Nội vụ", "Sở Tư pháp", "Sở Tài chính", "Sở Công Thương", "Sở Nông nghiệp và Môi trường", "Sở Xây dựng",
      "Sở Khoa học và Công nghệ", "Sở Văn hóa, Thể thao và Du lịch", "Sở Giáo dục và Đào tạo", "Sở Y tế",
      "Thanh tra tỉnh", "Sở Dân tộc và Tôn giáo"]
BASE_M = {"ubnd_tinh": 0.62, "van_phong": 0.66, "so_nganh": 0.56, "ubnd_xa": 0.38, "thpt": 0.48, "thcs": 0.38,
          "tieu_hoc": 0.35, "mam_non": 0.26}
HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Võ", "Huỳnh", "Đặng", "Bùi", "Đỗ", "Phan"]
DEM = ["Văn", "Thị", "Minh", "Thanh", "Hoàng", "Ngọc", "Quốc", "Thu"]
TEN = ["An", "Bình", "Cường", "Dũng", "Hà", "Hải", "Hùng", "Lan", "Linh", "Long", "Mai", "Nam", "Phúc", "Quang", "Tâm", "Trang", "Tuấn", "Vy"]


def person():
    return f"{random.choice(HO)} {random.choice(DEM)} {random.choice(TEN)}"


def slug(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.replace("Đ", "D").replace("đ", "d"))
    return "".join(c for c in s if c.isalnum() and ord(c) < 128).lower()


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="Khởi tạo CSDL DTI Platform")
    ap.add_argument("--blank", action="store_true", help="Hệ thống trống cho tỉnh mới (không có dữ liệu mẫu)")
    ap.add_argument("--province", default="Tây Ninh", help="Tên tỉnh/thành phố (VD: Bình Phước)")
    ap.add_argument("--type", default="Tỉnh", choices=["Tỉnh", "Thành phố"], help="Tỉnh hoặc Thành phố")
    ap.add_argument("--org", default=None, help="Đơn vị chủ quản (mặc định: Sở Khoa học và Công nghệ <tỉnh>)")
    ap.add_argument("--admin-password", default=None, help="Mật khẩu ban đầu của admin (bản trống: bắt buộc đổi khi đăng nhập)")
    return ap.parse_args()


def seed_assessments(db, periods, units, users, kh_ub):
    """Quy trình đánh giá: các kỳ trước đã được UBND tỉnh công bố; kỳ hiện hành đang tự đánh giá / thẩm định."""
    from app.models import Assessment, DTIScore, UnitMetric
    from app.routers.assessments import _estimate, _get_or_create
    print("9) Quy trình tự đánh giá → thẩm định → công bố ...")
    for i, p in enumerate(periods):
        if p.is_current:
            continue
        p.published_at = datetime.combine(p.end_date + timedelta(days=25), datetime.min.time()) + timedelta(hours=9)
        p.published_by, p.publish_decision = "Chủ tịch UBND tỉnh", f"{1200 + 37 * i}/QĐ-UBND"
        p.is_locked = p.year < TODAY.year  # số liệu các năm trước đã khóa
    cur = next(p for p in periods if p.is_current)
    cur_vals = {(u, c): r for u, c, r in db.execute(select(UnitMetric.unit_id, UnitMetric.criterion_id, UnitMetric.raw_value)
                                                   .where(UnitMetric.period_id == cur.id, UnitMetric.source == "survey"))}
    by_name = {u.username: u for u in users}
    thcs = by_name["truong.thcs"].unit
    others_hc = [u for u in units if u.unit_type == "hanh_chinh" and u.id != kh_ub.id][:14]
    others_gd = [u for u in units if u.unit_type == "giao_duc" and u.id != thcs.id][:10]
    now = datetime.now()

    def fill(a):
        for it in a.items:
            it.value_raw = (cur_vals.get((a.unit_id, it.criterion_id)) or it.value_raw
                            or ("Có" if it.criterion.metric_type == "boolean" else "0"))
            it.evidence = f"Báo cáo số liệu {it.criterion.code} – {a.unit.name}"
        a.self_score = _estimate(a.items)

    # phường Khánh Hậu: công chức đang lập phiếu (gợi ý sẵn giá trị kỳ trước)
    a = _get_or_create(db, kh_ub, cur, by_name["cb.khanhhau"])
    for it in a.items[:len(a.items) // 2]:
        it.evidence = "Văn bản/biểu mẫu minh chứng của phường"
    a.self_score = _estimate(a.items)
    # THCS Khánh Hậu: đã nộp, chờ Sở GD&ĐT thẩm định
    a = _get_or_create(db, thcs, cur, by_name["gv.thcs"])
    fill(a)
    a.status, a.submitted_by, a.submitted_at = "da_nop", by_name["truong.thcs"].full_name, now - timedelta(days=1)
    for j, u in enumerate(others_hc + others_gd):
        a = _get_or_create(db, u, cur, None)
        a.prepared_by = "Cán bộ phụ trách"
        fill(a)
        if j % 3 == 0:  # đã nộp, chờ thẩm định
            a.status, a.submitted_by, a.submitted_at = "da_nop", "Lãnh đạo đơn vị", now - timedelta(days=2 + j % 4)
        elif j % 3 == 1:  # đã thẩm định
            d = db.scalar(select(DTIScore).where(DTIScore.unit_id == u.id, DTIScore.period_id == cur.id))
            a.status, a.submitted_by, a.submitted_at = "da_tham_dinh", "Lãnh đạo đơn vị", now - timedelta(days=8)
            a.reviewed_by = "Lãnh đạo Sở GD&ĐT" if u.unit_type == "giao_duc" else "Chuyên viên Sở KH&CN"
            a.reviewed_at, a.final_score = now - timedelta(days=4), (d.score if d else None)
    db.commit()
    n = db.scalar(select(text("count(*)")).select_from(Assessment))
    print(f"   {sum(1 for p in periods if p.published_at)} kỳ đã công bố · {n} phiếu tự đánh giá kỳ {cur.code}")


def write_settings(db, items: dict):
    from app.models import SystemSetting
    for k, v in items.items():
        db.merge(SystemSetting(key=k, value=v, updated_by="khoi_tao"))


def main():
    args = parse_args()
    print("1) Tạo lại schema & bảng ...")
    with engine.begin() as c:
        for s in ("gold", "silver", "bronze"):
            c.execute(text(f"DROP SCHEMA IF EXISTS {s} CASCADE"))
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    init_schemas()
    Base.metadata.create_all(engine)
    from app.services.bi import create_bi_views
    create_bi_views(engine)
    db = SessionLocal()

    # -------- quyền & vai trò
    perms = {code: Permission(code=code, name=n, module=m) for code, n, m in PERMISSIONS}
    db.add_all(perms.values())
    roles = {}
    for i, (code, name, desc, scope, level, duties, plist) in enumerate(ROLES):
        roles[code] = Role(code=code, name=name, description=desc, data_scope=scope, level=level, duties=duties,
                           sort_order=i, permissions=[perms[p] for p in plist])
    db.add_all(roles.values())

    # -------- bộ tiêu chí
    pillars = {}
    for i, (code, name, desc, w) in enumerate(PILLARS):
        pillars[code] = Pillar(code=code, name=name, description=desc, weight=w, sort_order=i)
    db.add_all(pillars.values())
    db.flush()
    crits = {}
    for code, pc, name, ut, mt, target, w, label, src, _ in CRITERIA:
        crits[code] = Criterion(code=code, pillar_id=pillars[pc].id, name=name, unit_type=ut, metric_type=mt,
                                target=target, weight=w, unit_label=label, source=src)
    db.add_all(crits.values())
    for code, name, pc, trig, ut, desc, actions, svcs, cost, months in SOLUTIONS:
        db.add(SolutionGroup(code=code, name=name, pillar_id=pillars[pc].id, trigger_criteria=trig, unit_type=ut,
                             description=desc, actions=actions, service_codes=svcs, cost_level=cost, duration_months=months))
    services = {}
    for code, name, cat, pc, uts, price, desc in SERVICES:
        services[code] = ServiceCatalog(code=code, name=name, category=cat, pillar_code=pc, unit_types=uts,
                                        monthly_price=price, description=desc)
    db.add_all(services.values())

    # -------- kỳ đánh giá: 2025-Q1 → quý hiện tại
    periods = []
    cur_q = (TODAY.month - 1) // 3 + 1
    for y in (2025, 2026):
        for q in range(1, 5):
            if (y, q) > (TODAY.year, cur_q):
                break
            sd = date(y, 3 * q - 2, 1)
            ed = (date(y + (q == 4), (3 * q) % 12 + 1, 1) - timedelta(days=1))
            periods.append(Period(code=f"{y}-Q{q}", name=f"Quý {q}/{y}", year=y, quarter=q, start_date=sd, end_date=ed,
                                  is_current=(y, q) == (TODAY.year, cur_q)))
    db.add_all(periods)
    db.flush()
    print(f"   {len(periods)} kỳ đánh giá: {periods[0].code} → {periods[-1].code}")

    label = f"{args.type} {args.province}"
    org = args.org or f"Sở Khoa học và Công nghệ {args.type.lower()} {args.province}"
    if args.blank:
        # ---- HỆ THỐNG TRỐNG CHO TỈNH MỚI: chỉ giữ kỳ hiện hành và vài kỳ gần nhất, không có dữ liệu mẫu
        for p_ in periods[:-4]:
            db.delete(p_)
        tinh = Region(code="TINH", name=label, type="tinh")
        db.add(tinh)
        pw_admin = args.admin_password or "Admin@123"
        db.add(User(username="admin", full_name="Quản trị hệ thống", role_id=roles["admin"].id, position="Quản trị viên",
                    password_hash=hash_password(pw_admin), must_change_password=True))
        write_settings(db, {"province_name": args.province, "province_type": args.type, "org_name": org, "demo_mode": False,
                            "password_min_length": 8, "password_require_complex": True})
        db.commit()
        db.close()
        print(f"Đã khởi tạo hệ thống TRỐNG cho {label}.")
        print(f"   Đăng nhập: admin / {pw_admin}  (bắt buộc đổi mật khẩu ở lần đầu)")
        print("   Tiếp theo: Quản trị → Thiết lập tỉnh mới (nhập danh mục địa bàn, đơn vị, tài khoản...)")
        return
    write_settings(db, {"province_name": args.province, "province_type": args.type, "org_name": org})

    # -------- địa bàn & đơn vị
    print("2) Địa bàn & đơn vị ...")
    tinh = Region(code="TN", name=label, type="tinh", population=3254000, area_km2=8536.5)
    db.add(tinh)
    db.flush()
    regions = []
    for i, n in enumerate(PHUONG + XA, 1):
        typ = "phuong" if n in PHUONG else "xa"
        regions.append(Region(code=f"R{i:02d}", name=("Phường " if typ == "phuong" else "Xã ") + n, type=typ,
                              parent_id=tinh.id, population=random.randint(25, 110) * 1000,
                              area_km2=round(random.uniform(15, 260), 1)))
    db.add_all(regions)
    db.flush()

    units: list[Unit] = []
    maturity: dict[str, float] = {}

    def add_unit(code, name, ut, cat, level, region, parent=None, staff=None, students=None):
        u = Unit(code=code, name=name, unit_type=ut, category=cat, level=level, region_id=region.id,
                 parent_unit_id=parent.id if parent else None, head_name=person(),
                 address=f"{region.name}, tỉnh Tây Ninh", phone=f"0272{random.randint(3000000, 3999999)}",
                 email=f"{slug(name)[:30]}@tayninh.gov.vn" if ut == "hanh_chinh" else f"{slug(name)[:30]}@tayninh.edu.vn",
                 staff_count=staff, student_count=students)
        db.add(u)
        db.flush()
        units.append(u)
        bonus = 0.06 if region.type == "phuong" else 0
        maturity[code] = float(np.clip(np.random.normal(BASE_M[cat] + bonus, 0.13), 0.08, 0.95))
        return u

    ubnd_tinh = add_unit("HC.T01", "Ủy ban nhân dân tỉnh Tây Ninh", "hanh_chinh", "ubnd_tinh", "tinh", tinh, staff=60)
    vp = add_unit("HC.T02", "Văn phòng UBND tỉnh Tây Ninh", "hanh_chinh", "van_phong", "tinh", tinh, ubnd_tinh, staff=85)
    so_units = {}
    for i, n in enumerate(SO, 1):
        so_units[n] = add_unit(f"HC.S{i:02d}", f"{n} tỉnh Tây Ninh", "hanh_chinh", "so_nganh", "tinh", tinh, ubnd_tinh,
                               staff=random.randint(45, 140))
    so_gd = so_units["Sở Giáo dục và Đào tạo"]
    so_kh = so_units["Sở Khoa học và Công nghệ"]
    so_nv = so_units["Sở Nội vụ"]
    ubnd_xa = {}
    for r in regions:
        n = r.name
        ub = add_unit(f"HC.{r.code}", f"UBND {n}", "hanh_chinh", "ubnd_xa", "xa", r, staff=random.randint(35, 70))
        ubnd_xa[r.code] = ub
        add_unit(f"GD.{r.code}.MN1", f"Trường Mầm non {n.split(' ', 1)[1]}", "giao_duc", "mam_non", "xa", r, ub,
                 staff=random.randint(15, 35), students=random.randint(150, 450))
        n_th = 2 if r.population > 60000 else 1
        for k in range(1, n_th + 1):
            suffix = f" {'AB'[k - 1]}" if n_th > 1 else ""
            add_unit(f"GD.{r.code}.TH{k}", f"Trường Tiểu học {n.split(' ', 1)[1]}{suffix}", "giao_duc", "tieu_hoc", "xa", r, ub,
                     staff=random.randint(25, 55), students=random.randint(400, 1200))
        add_unit(f"GD.{r.code}.THCS1", f"Trường THCS {n.split(' ', 1)[1]}", "giao_duc", "thcs", "xa", r, ub,
                 staff=random.randint(30, 60), students=random.randint(500, 1400))
        if r.type == "phuong" or random.random() < 0.35:
            add_unit(f"GD.{r.code}.THPT1", f"Trường THPT {n.split(' ', 1)[1]}", "giao_duc", "thpt", "tinh", r, so_gd,
                     staff=random.randint(50, 95), students=random.randint(800, 1800))
    # Ví dụ trong quy trình: Phường Khánh Hậu khá tốt
    kh_region = next(r for r in regions if r.name == "Phường Khánh Hậu")
    maturity[f"HC.{kh_region.code}"] = 0.6
    print(f"   {len(regions)} xã/phường, {len(units)} đơn vị")

    # -------- hạ tầng & dịch vụ (ảnh chụp hiện tại)
    print("3) Hạ tầng & dịch vụ số ...")
    m_now = {}
    for u in units:
        m = min(maturity[u.code] + 0.017 * (len(periods) - 1), 0.98)
        m_now[u.code] = m
        db.add(UnitInfra(
            unit_id=u.id, computers=int((u.staff_count or 20) * np.clip(m + random.uniform(0, 0.3), 0.3, 1.1)),
            servers=random.randint(0, 3) if u.level == "tinh" else random.randint(0, 1),
            internet_mbps=int(np.clip(random.choice([50, 100, 150, 200, 300, 500]) * (0.6 + m), 30, 1000)),
            has_lan=random.random() < 0.6 + m / 2, has_wifi=random.random() < 0.5 + m / 2,
            has_firewall=random.random() < sigmoid((m - 0.5) * 7), has_backup=random.random() < sigmoid((m - 0.55) * 7),
            has_camera=random.random() < m, smart_classrooms=int(random.random() * 10 * m) if u.unit_type == "giao_duc" else 0,
        ))
        for code, sv in services.items():
            if u.unit_type not in sv.unit_types:
                continue
            base = {"VBDH": 0.97, "SMARTCA": 0.85, "FIBER": 0.95, "IGATE": 0.9 if u.category in ("ubnd_xa", "so_nganh") else 0.2,
                    "VNEDU": 0.92, "TSLCD": 0.7 if u.unit_type == "hanh_chinh" else 0}.get(code, 0.15 + 0.6 * m)
            r = random.random()
            if r < base:
                status = "dang_dung" if random.random() < 0.92 else "dung_thu"
            elif r < base + 0.06:
                status = "het_han"
            else:
                continue
            start = TODAY - timedelta(days=random.randint(90, 900))
            end = TODAY + timedelta(days=random.randint(-40, 420))
            if status == "het_han":
                end = TODAY - timedelta(days=random.randint(5, 120))
            db.add(UnitService(unit_id=u.id, service_id=sv.id, status=status, start_date=start, end_date=end,
                               usage_level=int(np.clip(np.random.normal(30 + 60 * m, 15), 5, 100)),
                               monthly_fee=sv.monthly_price))
    db.commit()

    # -------- người dùng
    print("4) Người dùng ...")
    pw = hash_password("123456")
    kh_ub = ubnd_xa[kh_region.code]
    kh_school = next(u for u in units if u.code == f"GD.{kh_region.code}.THCS1")
    users = [
        User(username="admin", full_name="Quản trị hệ thống", role_id=roles["admin"].id, unit_id=so_kh.id, position="Quản trị viên"),
        User(username="lanhdao.tinh", full_name="Lãnh đạo UBND tỉnh", role_id=roles["lanh_dao_tinh"].id, unit_id=ubnd_tinh.id, position="Phó Chủ tịch UBND tỉnh"),
        User(username="vp.ubndtinh", full_name="Chuyên viên VP UBND tỉnh", role_id=roles["vp_ubnd_tinh"].id, unit_id=vp.id, position="Chuyên viên Phòng Kiểm soát TTHC – theo dõi nhiệm vụ"),
        User(username="skhcn", full_name="Chuyên viên dữ liệu Sở KH&CN", role_id=roles["chuyen_vien_du_lieu"].id, unit_id=so_kh.id, position="Chuyên viên Phòng CĐS"),
        User(username="sgddt", full_name="Lãnh đạo Sở GD&ĐT", role_id=roles["lanh_dao_so_gd"].id, unit_id=so_gd.id, position="Phó Giám đốc Sở"),
        User(username="lanhdao.stp", full_name="Giám đốc Sở Tư pháp", role_id=roles["lanh_dao_co_quan"].id, unit_id=so_units["Sở Tư pháp"].id, position="Giám đốc Sở"),
        User(username="khanhhau", full_name="Chủ tịch UBND phường Khánh Hậu", role_id=roles["lanh_dao_xa"].id, unit_id=kh_ub.id, region_id=kh_region.id, position="Chủ tịch UBND phường"),
        User(username="vanthu.khanhhau", full_name="Văn thư UBND phường Khánh Hậu", role_id=roles["van_thu_xa"].id, unit_id=kh_ub.id, region_id=kh_region.id, position="Văn thư – Văn phòng HĐND và UBND"),
        User(username="tp.khanhhau", full_name="Trưởng phòng VH-XH phường Khánh Hậu", role_id=roles["truong_phong_xa"].id, unit_id=kh_ub.id, region_id=kh_region.id, position="Trưởng phòng Văn hóa – Xã hội"),
        User(username="cb.khanhhau", full_name="Công chức phụ trách CĐS phường Khánh Hậu", role_id=roles["cong_chuc_xa"].id, unit_id=kh_ub.id, region_id=kh_region.id, position="Công chức Phòng Văn hóa – Xã hội"),
        User(username="truong.thcs", full_name=f"Hiệu trưởng {kh_school.name}", role_id=roles["hieu_truong"].id, unit_id=kh_school.id, region_id=kh_region.id, position="Hiệu trưởng"),
        User(username="gv.thcs", full_name=f"Giáo viên Tin học {kh_school.name}", role_id=roles["can_bo_truong"].id, unit_id=kh_school.id, region_id=kh_region.id, position="Giáo viên phụ trách CNTT"),
        User(username="qt.khanhhau", full_name="Quản trị hệ thống phường Khánh Hậu", role_id=roles["quan_tri_xa"].id, unit_id=kh_ub.id, region_id=kh_region.id, position="Công chức Văn phòng – phụ trách CNTT"),
        User(username="am01", full_name="Nhân viên AM khu vực 1", role_id=roles["am"].id, position="AM khối Chính quyền – Giáo dục"),
        User(username="am02", full_name="Nhân viên AM khu vực 2", role_id=roles["am"].id, position="AM khối Chính quyền – Giáo dục"),
    ]
    for u in users:
        u.password_hash = pw
        u.password_changed_at = datetime.now()
        u.email = f"{u.username}@demo.local"
    db.add_all(users)
    db.flush()
    am_regions = {"am01": regions[:12], "am02": regions[12:26]}
    for un, rs in am_regions.items():
        uid = next(u.id for u in users if u.username == un)
        rids = {r.id for r in rs}
        for unit in units:
            if unit.region_id in rids:
                db.add(AMAssignment(user_id=uid, unit_id=unit.id))
    db.commit()

    # -------- nhiệm vụ (liên thông VBĐH)
    print("5) Nhiệm vụ giao & trạng thái xử lý ...")
    admin_xa = [ubnd_xa[r.code] for r in regions]
    schools = [u for u in units if u.unit_type == "giao_duc"]
    task_templates = [
        (ubnd_tinh, "Triển khai Kế hoạch chuyển đổi số năm {y} trên địa bàn xã, phường", "ke_hoach", "NT", admin_xa),
        (so_kh, "Báo cáo tình hình chuyển đổi số cấp xã {q}", "cong_van", "HD", admin_xa),
        (so_nv, "Rà soát, cập nhật dữ liệu cán bộ, công chức trên phần mềm quản lý {q}", "cong_van", "NL", admin_xa),
        (vp, "Báo cáo kết quả giải quyết TTHC trực tuyến toàn trình {q}", "cong_van", "DV", admin_xa),
        (so_gd, "Báo cáo triển khai học bạ số và sổ điểm điện tử {q}", "cong_van", "DV", schools),
        (so_gd, "Rà soát hạ tầng CNTT, thiết bị dạy học số {q}", "cong_van", "HT", schools),
        (so_kh, "Tự đánh giá mức độ bảo đảm an toàn thông tin {q}", "cong_van", "AT", admin_xa + schools[::3]),
    ]
    tcount = 0
    for p in periods:
        for assigner, title, dtype, pcode, targets in task_templates:
            if "Kế hoạch" in title and p.quarter != 1:
                continue
            if p.is_current and random.random() < 0.3:
                continue
            tcount += 1
            ddate = p.start_date + timedelta(days=random.randint(3, 20))
            deadline = min(ddate + timedelta(days=random.randint(25, 50)), p.end_date)
            t = Task(code=f"NV-{p.year}-{tcount:04d}", title=title.format(y=p.year, q=p.name.lower()), doc_type=dtype,
                     content="Đề nghị các đơn vị triển khai thực hiện và báo cáo kết quả về cơ quan giao nhiệm vụ đúng thời hạn.",
                     doc_number=f"{random.randint(100, 4999)}/{'UBND-VP' if assigner is ubnd_tinh else 'VP-KSTT' if assigner is vp else 'S' + assigner.code[-2:]}",
                     doc_date=ddate, assigner_unit_id=assigner.id, deadline=deadline, pillar_code=pcode,
                     priority="khan" if random.random() < 0.15 else "thuong", created_by=users[0].id,
                     created_at=datetime.combine(ddate, datetime.min.time()) + timedelta(hours=8))
            db.add(t)
            db.flush()
            for unit in targets:
                m = maturity[unit.code] + 0.017 * periods.index(p)
                a = TaskAssignment(task_id=t.id, unit_id=unit.id, role="chu_tri")
                recv = datetime.combine(ddate, datetime.min.time()) + timedelta(days=random.randint(0, 4), hours=9)
                if deadline < TODAY:
                    r = random.random()
                    p_on = 0.35 + 0.6 * m
                    if r < p_on:
                        st, conf = "hoan_thanh", deadline - timedelta(days=random.randint(0, 12))
                    elif r < p_on + (1 - p_on) * 0.55:
                        st, conf = "hoan_thanh", deadline + timedelta(days=random.randint(1, 20))
                    else:
                        st, conf = random.choice(["dang_xu_ly", "da_bao_cao", "tra_lai", "chua_tiep_nhan"]), None
                    if conf and conf > TODAY:
                        conf = TODAY
                else:
                    st = random.choices(["chua_tiep_nhan", "dang_xu_ly", "da_bao_cao", "hoan_thanh"], [0.2, 0.45, 0.15, 0.2])[0]
                    conf = TODAY - timedelta(days=random.randint(0, 5)) if st == "hoan_thanh" else None
                a.status = st
                if st != "chua_tiep_nhan":
                    a.received_at = recv
                    a.handler_dept = "Phòng Văn hóa – Xã hội" if unit.unit_type == "hanh_chinh" else "Tổ chuyên môn"
                    a.handler_name = person()
                    a.progress = random.randint(20, 90)
                if st in ("da_bao_cao", "hoan_thanh", "tra_lai"):
                    a.progress = 100 if st != "tra_lai" else 80
                    a.report_doc_number = f"{random.randint(10, 999)}/BC-{unit.code.replace('.', '')}"
                    a.reported_at = datetime.combine(conf or min(deadline, TODAY), datetime.min.time()) - timedelta(days=1, hours=-10)
                if st == "tra_lai":
                    a.return_reason = "Đề nghị bổ sung số liệu chi tiết theo biểu mẫu"
                if conf:
                    a.confirmed_at = datetime.combine(conf, datetime.min.time()) + timedelta(hours=15)
                db.add(a)
            db.add(TaskLog(task_id=t.id, user_id=users[0].id, action="giao_nhiem_vu",
                           note=f"Phát hành văn bản {t.doc_number} đến {len(targets)} đơn vị", created_at=t.created_at))
    # ---- Kịch bản liên thông 3 cấp: UBND tỉnh → UBND xã/phường → trường học (kỳ hiện tại)
    now = datetime.now()
    tcount += 1
    root = Task(code=f"NV-{TODAY.year}-{tcount:04d}",
                title="Triển khai chuyển đổi số trong trường học năm học 2026–2027 (học bạ số, sổ điểm điện tử, hạ tầng CNTT)",
                content="UBND các xã, phường chỉ đạo các trường mầm non, tiểu học, THCS trên địa bàn triển khai, "
                        "tổng hợp kết quả và báo cáo UBND tỉnh (qua Văn phòng UBND tỉnh).",
                doc_number=f"{random.randint(4000, 4999)}/UBND-VX", doc_date=TODAY - timedelta(days=10), doc_type="ke_hoach",
                assigner_unit_id=ubnd_tinh.id, deadline=TODAY + timedelta(days=20), pillar_code="DV", priority="khan",
                created_by=users[1].id, created_at=now - timedelta(days=10))
    db.add(root)
    db.flush()
    db.add(TaskLog(task_id=root.id, user_id=users[1].id, action="giao_nhiem_vu", created_at=root.created_at,
                   note=f"Phát hành văn bản {root.doc_number} đến {len(admin_xa)} UBND xã, phường"))
    n_child = 0
    for ub in admin_xa:
        is_kh = ub.id == kh_ub.id
        r = 0.5 if is_kh else random.random()
        a = TaskAssignment(task_id=root.id, unit_id=ub.id, role="chu_tri")
        db.add(a)
        if r < 0.12:  # chưa tiếp nhận
            continue
        a.status, a.received_at = "dang_xu_ly", now - timedelta(days=9)
        a.handler_dept, a.handler_name = "Phòng Văn hóa – Xã hội", person()
        db.flush()
        if r < 0.2:  # đã tiếp nhận, chưa giao tiếp
            a.progress = 10
            continue
        tcount += 1
        n_child += 1
        sub_schools = [s for s in schools if s.region_id == ub.region_id and s.level == "xa"]
        child = Task(code=f"NV-{TODAY.year}-{tcount:04d}", title=root.title, content="Giao tiếp từ văn bản của UBND tỉnh. "
                     "Các trường triển khai và báo cáo kết quả về UBND xã/phường (Phòng Văn hóa – Xã hội).",
                     doc_number=f"{random.randint(100, 999)}/UBND-VHXH", doc_date=TODAY - timedelta(days=8), doc_type="cong_van",
                     assigner_unit_id=ub.id, deadline=TODAY + timedelta(days=12), pillar_code="DV", priority="khan",
                     parent_assignment_id=a.id, created_by=users[5].id if is_kh else None, created_at=now - timedelta(days=8))
        db.add(child)
        db.flush()
        db.add(TaskLog(task_id=root.id, assignment_id=a.id, action="giao_tiep", created_at=child.created_at,
                       note=f"[{ub.name}] giao tiếp cho {len(sub_schools)} trường ({child.code})"))
        db.add(TaskLog(task_id=child.id, action="giao_nhiem_vu", created_at=child.created_at,
                       note=f"Giao tiếp từ {root.code} (UBND tỉnh) – {len(sub_schools)} trường"))
        all_done = r > 0.75
        for i, s in enumerate(sub_schools):
            st = "hoan_thanh" if all_done else (["hoan_thanh", "da_bao_cao", "dang_xu_ly", "chua_tiep_nhan"][i % 4] if is_kh
                                                 else random.choices(["chua_tiep_nhan", "dang_xu_ly", "da_bao_cao", "hoan_thanh"], [0.15, 0.35, 0.2, 0.3])[0])
            ca = TaskAssignment(task_id=child.id, unit_id=s.id, role="chu_tri", status=st)
            if st != "chua_tiep_nhan":
                ca.received_at, ca.handler_dept, ca.handler_name = now - timedelta(days=7), "Tổ chuyên môn", person()
                ca.progress = random.randint(30, 80)
            if st in ("da_bao_cao", "hoan_thanh"):
                ca.progress, ca.report_doc_number = 100, f"{random.randint(10, 99)}/BC-{s.code.replace('.', '')}"
                ca.reported_at = now - timedelta(days=random.randint(1, 4))
            if st == "hoan_thanh":
                ca.confirmed_at = now - timedelta(days=random.randint(0, 1))
            db.add(ca)
        done = sum(1 for _ in sub_schools) if all_done else None
        a.progress = 90 if all_done else random.randint(20, 60)
        if all_done and r > 0.88:  # xã đã tổng hợp báo cáo lên tỉnh
            a.status, a.progress = ("hoan_thanh" if r > 0.95 else "da_bao_cao"), 100
            a.report_doc_number, a.reported_at = f"{random.randint(100, 999)}/BC-UBND", now - timedelta(days=1)
            if a.status == "hoan_thanh":
                a.confirmed_at = now
    # Văn bản mới đến phường (chưa tiếp nhận) – để thử vai văn thư → lãnh đạo → trưởng phòng → công chức → ký báo cáo
    tcount += 1
    fresh = Task(code=f"NV-{TODAY.year}-{tcount:04d}", title="Báo cáo số liệu hạ tầng số và nền tảng số dùng chung cấp xã tháng 11/2026",
                 content="Đề nghị UBND các phường báo cáo số liệu theo biểu mẫu đính kèm, gửi về Sở KH&CN.",
                 doc_number=f"{random.randint(1000, 1999)}/SKHCN-CĐS", doc_date=TODAY - timedelta(days=1), assigner_unit_id=so_kh.id,
                 deadline=TODAY + timedelta(days=14), pillar_code="HT", created_by=users[3].id, created_at=now - timedelta(days=1))
    db.add(fresh)
    db.flush()
    for ub in [ubnd_xa[r.code] for r in regions if r.type == "phuong"]:
        db.add(TaskAssignment(task_id=fresh.id, unit_id=ub.id, role="chu_tri"))
    db.add(TaskLog(task_id=fresh.id, user_id=users[3].id, action="giao_nhiem_vu", created_at=fresh.created_at,
                   note=f"Phát hành văn bản {fresh.doc_number} đến 14 UBND phường"))
    db.commit()
    # người xử lý cụ thể tại phường Khánh Hậu (để minh họa chuyển giao khi cán bộ nghỉ việc)
    cb_user = next(u for u in users if u.username == "cb.khanhhau")
    kh_leader = next(u for u in users if u.username == "khanhhau")
    # hai văn bản đang ở bước soạn thảo văn bản trả lời (NĐ 30): chờ trưởng phòng kiểm tra · đã ký chờ văn thư phát hành
    for k, (title, st) in enumerate([("Báo cáo tình hình triển khai Đề án 06 trên địa bàn quý IV/2026", "cho_kiem_tra"),
                                     ("Báo cáo kết quả tuyên truyền, phổ biến kỹ năng số cho người dân tháng 11/2026", "cho_phat_hanh")]):
        tcount += 1
        tk = Task(code=f"NV-{TODAY.year}-{tcount:04d}", title=title, content="Đề nghị UBND phường báo cáo theo đề cương đính kèm.",
                  doc_number=f"{random.randint(2000, 2999)}/UBND-VX", doc_date=TODAY - timedelta(days=9 - k),
                  assigner_unit_id=ubnd_tinh.id, deadline=TODAY + timedelta(days=4 + k), pillar_code="HD",
                  created_by=users[1].id, created_at=now - timedelta(days=9 - k))
        db.add(tk)
        db.flush()
        ta = TaskAssignment(task_id=tk.id, unit_id=kh_ub.id, role="chu_tri", status=st, received_at=now - timedelta(days=8 - k),
                            leader_opinion="Giao Phòng VH-XH chủ trì tham mưu, báo cáo đúng hạn",
                            progress=90 if st == "cho_kiem_tra" else 100,
                            report_note="Dự thảo báo cáo đã hoàn thiện, kính trình trưởng phòng kiểm tra" if st == "cho_kiem_tra"
                            else "Báo cáo kết quả thực hiện (đã ký số)")
        if st == "cho_phat_hanh":
            ta.reviewed_by, ta.signed_by, ta.signed_at = "Trưởng phòng VH-XH", kh_leader.full_name, now - timedelta(hours=3)
        db.add(ta)
        db.add(TaskLog(task_id=tk.id, user_id=users[1].id, action="giao_nhiem_vu", created_at=tk.created_at,
                       note=f"Phát hành văn bản {tk.doc_number}"))
    db.flush()
    # văn bản đi: số đi theo đơn vị/năm, người ký, văn thư phát hành
    signers = {u.unit_id: u.full_name for u in users if u.unit_id and u.role.code in ("lanh_dao_xa", "hieu_truong", "lanh_dao_co_quan")}
    from app.routers.tasks import ABBR
    cnt_out = {}
    for a in db.scalars(select(TaskAssignment).where(TaskAssignment.reported_at.isnot(None)).order_by(TaskAssignment.reported_at)):
        k = (a.unit_id, a.reported_at.year)
        cnt_out[k] = cnt_out.get(k, 0) + 1
        a.outgoing_no = cnt_out[k]
        a.report_doc_number = f"{a.outgoing_no}/BC-{ABBR.get(a.unit.category, 'DV')}"
        a.signed_by = signers.get(a.unit_id, "Lãnh đạo đơn vị")
        a.signed_at = a.issued_at = a.reported_at
        a.issued_by = "Văn thư đơn vị"
    for a in db.scalars(select(TaskAssignment).where(TaskAssignment.unit_id == kh_ub.id,
                                                     TaskAssignment.status.in_(["dang_xu_ly", "tra_lai", "cho_duyet", "cho_kiem_tra", "cho_phat_hanh"]))):
        a.handler_dept, a.handler_name = "Phòng Văn hóa – Xã hội", cb_user.full_name
    # số đến (sổ văn bản đến theo đơn vị/năm) + thông báo ban đầu cho người dùng mẫu
    cnt = {}
    for a in db.scalars(select(TaskAssignment).where(TaskAssignment.received_at.isnot(None)).order_by(TaskAssignment.received_at)):
        k = (a.unit_id, a.received_at.year)
        cnt[k] = cnt.get(k, 0) + 1
        a.incoming_no = cnt[k]
    from app.routers.tasks import notify, unit_users
    user_units = {u.unit_id for u in users if u.unit_id}
    for a, t in db.execute(select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                           .where(TaskAssignment.unit_id.in_(user_units), TaskAssignment.status.in_(["chua_tiep_nhan", "cho_duyet", "tra_lai", "cho_kiem_tra", "cho_phat_hanh"]))):
        need, kind, title = {"chua_tiep_nhan": (("task.receive",), "van_ban_den", f"Văn bản đến: {t.title}"),
                             "cho_duyet": (("task.sign",), "trinh", f"Dự thảo chờ duyệt, ký: {t.title}"),
                             "cho_kiem_tra": (("task.review",), "trinh", f"Dự thảo chờ kiểm tra: {t.title}"),
                             "cho_phat_hanh": (("task.issue",), "trinh", f"Văn bản đã ký chờ cấp số, phát hành: {t.title}"),
                             "tra_lai": (("task.process",), "ket_qua", f"Cấp trên trả lại, yêu cầu bổ sung: {t.title}")}[a.status]
        notify(db, unit_users(db, a.unit_id, need), kind, title, t.id, f"{t.assigner.name} · hạn {t.deadline:%d/%m/%Y}")
    for a, t in db.execute(select(TaskAssignment, Task).join(Task, Task.id == TaskAssignment.task_id)
                           .where(Task.assigner_unit_id.in_(user_units), TaskAssignment.status == "da_bao_cao", Task.deadline >= TODAY)):
        notify(db, unit_users(db, t.assigner_unit_id, ("task.confirm",)), "bao_cao", f"{a.unit.name} đã gửi báo cáo: {t.title}", t.id)
    db.commit()
    print(f"   {tcount} nhiệm vụ (kịch bản 3 cấp: {n_child} xã đã giao tiếp xuống trường)")

    # -------- dữ liệu khảo sát từng kỳ → qua pipeline Bronze → Silver
    print("6) Dữ liệu khảo sát định kỳ → Bronze → Silver ...")
    SAMPLE_DIR.mkdir(exist_ok=True)
    crit_meta = {c[0]: c for c in CRITERIA}
    drop_units = set(random.sample([u.code for u in units], k=len(units) // 12))
    for pi, p in enumerate(periods):
        rows = []
        for u in units:
            growth = np.random.uniform(0.006, 0.028)
            m = maturity[u.code] + growth * pi
            if u.code in drop_units and pi == len(periods) - 1:
                m -= np.random.uniform(0.08, 0.16)
            m = float(np.clip(m, 0.03, 0.99))
            row = {"ma_don_vi": u.code, "ten_don_vi": u.name, "ky_danh_gia": p.code}
            for code, (_, _, _, ut, mt, target, _, _, src, off) in crit_meta.items():
                if src != "survey" and not (src in ("infra", "services") and not p.is_current):
                    continue
                if ut not in ("all", u.unit_type):
                    continue
                if random.random() < 0.03:
                    continue  # thiếu dữ liệu
                x = m + off + np.random.normal(0, 0.09)
                if mt == "boolean":
                    v = 1 if random.random() < sigmoid((x - 0.42) * 9) else 0
                    row[code] = random.choice(["Có", "x", "1", "có"]) if v else random.choice(["Không", "0", "không"])
                elif mt == "ratio":
                    v = float(np.clip(x * target * 1.05, 0, target)) if target < 100 else float(np.clip(x * 105, 0, 100))
                    r = random.random()
                    row[code] = f"{v:.0f}%" if r < 0.12 else (f"{v / 100:.2f}".replace(".", ",") if r < 0.17 else f"{v:.1f}")
                else:
                    v = float(np.clip(x * target * 1.1, 0, target * 1.6))
                    row[code] = f"{v:.0f}" if target > 10 else f"{v:.2f}"
            rows.append(row)
        # chèn lỗi dữ liệu có chủ đích để minh họa bước làm sạch
        rows.append({"ma_don_vi": "HC.X99", "ten_don_vi": "Đơn vị không có trong danh mục", "ky_danh_gia": p.code, "NT02": "80"})
        for _ in range(3):
            r = random.choice(rows[:-1])
            r[random.choice(["NT02", "HD01", "NL02"])] = random.choice(["abc", "120", "-5", "chưa rõ"])
        df = pd.DataFrame(rows)
        # Chỉ xuất file mẫu (để demo upload) cho kỳ hiện hành; các kỳ khác nạp trực tiếp
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        content = buf.getvalue().encode("utf-8-sig")
        if p.is_current:
            (SAMPLE_DIR / f"khao_sat_{p.code}.csv").write_bytes(content)
        b = pipeline.ingest_file(db, content, f"khao_sat_{p.code}.csv", users[3].id, p.code)
        b.uploaded_at = datetime.combine(min(p.end_date, TODAY), datetime.min.time()) + timedelta(hours=9)
        db.commit()
        pipeline.bronze_to_silver(db, b)
        print(f"   {p.code}: lô #{b.id} – {b.valid_values} giá trị hợp lệ, {b.rejected_values} bị loại")

    print("7) Đồng bộ chỉ số từ dữ liệu vận hành ...")
    for p in periods:
        parts = ("tasks", "infra", "services") if p.is_current else ("tasks",)
        b = pipeline.sync_operational(db, p, users[3].id, parts)
        b.status = "gold"
    db.commit()

    print("8) Tính Gold: điểm tiêu chí, trụ cột, DTI, cảnh báo, đề xuất + ML ...")
    for p in periods:
        res = scoring.compute_period(db, p)
        cl = ml.run_clustering(db, p)
        print(f"   {res} | silhouette={cl.get('silhouette')}")
    db.execute(text("UPDATE bronze.ingest_batches SET status='gold' WHERE status='silver'"))
    db.commit()
    seed_assessments(db, periods, units, users, kh_ub)

    # file mẫu bổ sung (định dạng dài, có lỗi) cho người dùng thử upload
    sample = pd.DataFrame([
        {"ma_don_vi": f"HC.{kh_region.code}", "ky": periods[-1].code, "ma_tieu_chi": "DV01", "gia_tri": "92%"},
        {"ma_don_vi": f"HC.{kh_region.code}", "ky": periods[-1].code, "ma_tieu_chi": "HD04", "gia_tri": "0,8"},
        {"ma_don_vi": f"HC.{kh_region.code}", "ky": periods[-1].code, "ma_tieu_chi": "AT01", "gia_tri": "75"},
        {"ma_don_vi": f"GD.{kh_region.code}.THCS1", "ky": periods[-1].code, "ma_tieu_chi": "DV04", "gia_tri": "Có"},
        {"ma_don_vi": f"GD.{kh_region.code}.THCS1", "ky": periods[-1].code, "ma_tieu_chi": "HT03", "gia_tri": "40"},
        {"ma_don_vi": "GD.R99.TH1", "ky": periods[-1].code, "ma_tieu_chi": "DV04", "gia_tri": "Có"},
        {"ma_don_vi": f"HC.{kh_region.code}", "ky": "Quý 9/2026", "ma_tieu_chi": "DV01", "gia_tri": "90"},
        {"ma_don_vi": f"HC.{kh_region.code}", "ky": periods[-1].code, "ma_tieu_chi": "XX01", "gia_tri": "10"},
        {"ma_don_vi": f"HC.{kh_region.code}", "ky": periods[-1].code, "ma_tieu_chi": "NL02", "gia_tri": "150"},
    ])
    sample.to_csv(SAMPLE_DIR / "cap_nhat_bo_sung_dang_dai.csv", index=False, encoding="utf-8-sig")
    # kế hoạch cải thiện mẫu (phường Khánh Hậu) + kế hoạch chăm sóc mẫu của AM
    from app.models import CarePlan, ImprovementPlan, PlanItem, Recommendation
    cur_p = next(p for p in periods if p.is_current)
    kh_units = [u.id for u in units if u.region_id == kh_region.id]
    recs = db.scalars(select(Recommendation).where(Recommendation.period_id == cur_p.id, Recommendation.unit_id.in_(kh_units),
                                                   Recommendation.priority_level.in_(["cao", "trung_binh"]))).all()
    if recs:
        plan = ImprovementPlan(title=f"Kế hoạch nâng cao mức độ chuyển đổi số phường Khánh Hậu {cur_p.name}", scope="region",
                               region_id=kh_region.id, period_id=cur_p.id, owner_unit_id=kh_ub.id, status="ban_hanh",
                               created_by=next(u.id for u in users if u.username == "khanhhau"))
        db.add(plan)
        db.flush()
        for i, r in enumerate(recs[:10]):
            g = r.solution
            st = ["hoan_thanh", "dang_lam", "chua_lam"][i % 3]
            db.add(PlanItem(plan_id=plan.id, unit_id=r.unit_id, solution_group_id=g.id, action=g.actions,
                            responsible="Người đứng đầu đơn vị", start_date=TODAY - timedelta(days=20),
                            end_date=TODAY + timedelta(days=30 * g.duration_months - 20), priority=r.priority_level,
                            cost_level=g.cost_level, status=st, progress={"hoan_thanh": 100, "dang_lam": 50, "chua_lam": 0}[st],
                            baseline_score=round(100 - r.priority_score, 1)))
    am_id = next(u.id for u in users if u.username == "am01")
    for j, unit in enumerate([u for u in units if u.region_id in {r.id for r in am_regions["am01"]}][:6]):
        db.add(CarePlan(unit_id=unit.id, am_user_id=am_id, activity=["tu_van", "tap_huan", "gia_han"][j % 3],
                        title=["Tư vấn giải pháp hội nghị trực tuyến", "Tập huấn khai thác VBĐH, chữ ký số", "Gia hạn Internet cáp quang"][j % 3],
                        planned_date=TODAY + timedelta(days=7 * (j - 2)), status="da_thuc_hien" if j < 2 else "ke_hoach",
                        result="Đơn vị đồng ý triển khai thử" if j < 2 else None))
    db.commit()
    # nhật ký mẫu cho chức năng cảnh báo bảo mật
    from app.models import AuditLog
    base = datetime.now() - timedelta(days=2)
    for i in range(4):
        db.add(AuditLog(username="tp.khanhhau", action="login_failed", entity="user", ip="113.161.45.20",
                        detail={"reason": "sai_mat_khau", "failed": i + 1}, created_at=base + timedelta(minutes=i)))
    db.add(AuditLog(username="skhcn", action="login", ip="27.72.100.8",
                    created_at=(datetime.now() - timedelta(days=1)).replace(hour=23, minute=12)))
    db.commit()
    db.close()
    print("Hoàn tất. Tài khoản demo: admin / 123456 (xem README để biết các vai trò khác)")


if __name__ == "__main__":
    main()
