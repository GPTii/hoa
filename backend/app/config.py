from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://dti:dtipass@localhost:5433/dti_platform"
    jwt_secret: str = "change-me-in-production"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 60 * 12
    demo_mode: bool = True  # hiện danh sách tài khoản thử nghiệm ở trang đăng nhập; tắt khi triển khai thật
    upload_dir: str = "uploads"
    cors_origins: str ="http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
