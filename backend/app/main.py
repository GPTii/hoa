from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .security import decode_token
from .routers import admin, admin_ops, am, analytics, assessments, auth, catalog, data, integration, notifications, plans, reports, tasks, workspace

app = FastAPI(
    title="DTI Platform – Nền tảng Trí tuệ Dữ liệu hỗ trợ quản trị chuyển đổi số",
    description="Cơ quan hành chính & cơ sở giáo dục – dùng chung cho các tỉnh/thành theo mô hình chính quyền địa phương 2 cấp",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def log_server_errors(request, call_next):
    """Ghi lỗi máy chủ (5xx) vào bảng api_errors để quản trị giám sát."""
    def save(status, msg):
        try:
            from .db import SessionLocal
            from .models import ApiError
            with SessionLocal() as s:
                s.add(ApiError(method=request.method, path=request.url.path[:300], status=status, message=msg[:2000]))
                s.commit()
        except Exception:  # noqa: BLE001
            pass
    try:
        resp = await call_next(request)
    except Exception as e:  # noqa: BLE001
        save(500, f"{type(e).__name__}: {e}")
        return JSONResponse(status_code=500, content={"detail": "Lỗi máy chủ, đã ghi nhận để quản trị kiểm tra"})
    if resp.status_code >= 500 and request.url.path.startswith("/api/"):
        save(resp.status_code, "HTTP " + str(resp.status_code))
    return resp


@app.middleware("http")
async def read_only_impersonation(request, call_next):
    """Phiên 'xem dưới vai trò' của quản trị chỉ được XEM: chặn mọi thao tác ghi (trừ trở về quản trị)."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path not in ("/api/auth/stop-impersonate", "/api/auth/logout"):
        auth = request.headers.get("authorization", "")
        payload = decode_token(auth[7:]) if auth.lower().startswith("bearer ") else None
        if payload and payload.get("imp_by"):
            return JSONResponse(status_code=403, content={
                "detail": "Đang xem thử dưới vai trò người dùng khác – chế độ chỉ xem, không thực hiện thao tác thay người dùng."})
    return await call_next(request)


for r in (auth, admin_ops, admin, catalog, analytics, data, tasks, am, reports, workspace, notifications, integration, plans, assessments):
    app.include_router(r.router)


@app.on_event("startup")
def ensure_bi_views():
    """Tạo/cập nhật các view phục vụ Power BI (gold.v_bi_*)."""
    try:
        from .db import engine
        from .services.bi import create_bi_views
        create_bi_views(engine)
    except Exception:  # noqa: BLE001 – CSDL chưa khởi tạo
        pass


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Phục vụ frontend đã build (frontend/dist) – chạy 1 cổng duy nhất khi triển khai
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(404, "Không tìm thấy API")
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
