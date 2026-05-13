from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlsplit


ROOT_DIR = Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _env_bool(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "HajiHaz AI")
    app_env: str = os.getenv("APP_ENV", "development")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    legacy_host_redirects_raw: str = os.getenv("LEGACY_HOST_REDIRECTS", "hajihaz.82.29.160.39.sslip.io").strip()
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@hajihaz.local")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "change-this-password")
    admin_password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "24"))
    user_session_ttl_hours: int = int(os.getenv("USER_SESSION_TTL_HOURS", "720"))
    auth_cookie_secure_raw: str = os.getenv("AUTH_COOKIE_SECURE", "").strip().lower()
    auth_cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", "true")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    ai_provider: str = os.getenv("AI_PROVIDER", "auto").strip().lower()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "800"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/api").rstrip("/")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    online_search_enabled: bool = _env_bool("ONLINE_SEARCH_ENABLED", "true")
    online_search_timeout_seconds: float = float(os.getenv("ONLINE_SEARCH_TIMEOUT_SECONDS", "8"))
    online_search_max_results: int = int(os.getenv("ONLINE_SEARCH_MAX_RESULTS", "3"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///backend/data/hajihaz.db")
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    app_log_path_raw: str = os.getenv("APP_LOG_PATH", "backend/data/hajihaz.log")
    alert_webhook_url: str = os.getenv("ALERT_WEBHOOK_URL", "")
    alert_email_host: str = os.getenv("ALERT_EMAIL_HOST", "").strip()
    alert_email_port: int = int(os.getenv("ALERT_EMAIL_PORT", "587"))
    alert_email_user: str = os.getenv("ALERT_EMAIL_USER", "").strip()
    alert_email_password: str = os.getenv("ALERT_EMAIL_PASSWORD", "").strip()
    alert_email_from: str = os.getenv("ALERT_EMAIL_FROM", "").strip()
    alert_email_to_raw: str = os.getenv("ALERT_EMAIL_TO", "").strip()
    alert_email_use_tls: bool = _env_bool("ALERT_EMAIL_USE_TLS", "true")
    log_tail_lines: int = int(os.getenv("LOG_TAIL_LINES", "80"))
    recent_alert_limit: int = int(os.getenv("RECENT_ALERT_LIMIT", "10"))
    recent_log_limit: int = int(os.getenv("RECENT_LOG_LIMIT", "25"))
    max_import_file_bytes: int = int(os.getenv("MAX_IMPORT_FILE_BYTES", str(8 * 1024 * 1024)))
    max_import_documents_per_request: int = int(os.getenv("MAX_IMPORT_DOCUMENTS_PER_REQUEST", "50"))
    request_log_retention_days: int = int(os.getenv("REQUEST_LOG_RETENTION_DAYS", "14"))
    alert_retention_days: int = int(os.getenv("ALERT_RETENTION_DAYS", "30"))
    health_check_retention_days: int = int(os.getenv("HEALTH_CHECK_RETENTION_DAYS", "30"))
    usage_event_retention_days: int = int(os.getenv("USAGE_EVENT_RETENTION_DAYS", "60"))
    metric_snapshot_retention_days: int = int(os.getenv("METRIC_SNAPSHOT_RETENTION_DAYS", "30"))
    backup_dir_raw: str = os.getenv("BACKUP_DIR", "backend/data/backups")
    backup_retention_days: int = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))
    backup_retention_count: int = int(os.getenv("BACKUP_RETENTION_COUNT", "12"))
    backup_interval_hours: int = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
    include_logs_in_backup: bool = _env_bool("INCLUDE_LOGS_IN_BACKUP", "true")
    ocr_enabled: bool = _env_bool("OCR_ENABLED", "true")
    ocr_languages: str = os.getenv("OCR_LANGUAGES", "eng")
    tesseract_command: str = os.getenv("TESSERACT_COMMAND", "tesseract").strip()
    pdftoppm_command: str = os.getenv("PDFTOPPM_COMMAND", "pdftoppm").strip()
    uvicorn_log_path_raw: str = os.getenv("UVICORN_LOG_PATH", "logs/app/uvicorn.log")
    log_file_retention_days: int = int(os.getenv("LOG_FILE_RETENTION_DAYS", "21"))
    metrics_snapshot_limit: int = int(os.getenv("METRICS_SNAPSHOT_LIMIT", "24"))
    analytics_window_days: int = int(os.getenv("ANALYTICS_WINDOW_DAYS", "14"))
    uploads_dir_raw: str = os.getenv("UPLOADS_DIR", "backend/data/uploads")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def public_host(self) -> str:
        if not self.public_base_url:
            return ""
        return urlsplit(self.public_base_url).netloc.lower()

    @property
    def google_login_enabled(self) -> bool:
        return bool(self.google_client_id)

    @property
    def auth_cookie_secure(self) -> bool:
        if self.auth_cookie_secure_raw:
            return self.auth_cookie_secure_raw in {"1", "true", "yes", "on"}
        return self.app_env != "development"

    @property
    def safe_auth_cookie_samesite(self) -> str:
        if self.auth_cookie_samesite in {"strict", "lax", "none"}:
            return self.auth_cookie_samesite
        return "lax"

    @property
    def legacy_host_redirects(self) -> List[str]:
        return [host.strip().lower() for host in self.legacy_host_redirects_raw.split(",") if host.strip()]

    @property
    def database_backend(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return "sqlite"
        if self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            return "postgresql"
        return "unsupported"

    @property
    def postgres_url(self) -> str:
        if self.database_backend != "postgresql":
            return ""
        return self.database_url

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError(
                "Only sqlite:/// DATABASE_URL values are active in this build. "
                "PostgreSQL DSNs are recognized for migration planning but require the planned data-layer upgrade."
            )
        return ROOT_DIR / self.database_url[len(prefix):]

    @property
    def app_log_path(self) -> Path:
        return ROOT_DIR / self.app_log_path_raw

    @property
    def backup_dir(self) -> Path:
        return ROOT_DIR / self.backup_dir_raw

    @property
    def uploads_dir(self) -> Path:
        return ROOT_DIR / self.uploads_dir_raw

    @property
    def uvicorn_log_path(self) -> Path:
        return ROOT_DIR / self.uvicorn_log_path_raw

    @property
    def alert_email_recipients(self) -> List[str]:
        return [item.strip() for item in self.alert_email_to_raw.split(",") if item.strip()]


settings = Settings()
