from __future__ import annotations

import tempfile
import unittest
import logging
from pathlib import Path

from fastapi.testclient import TestClient

import app.core.security as security_module
from app.core.config import settings
from app.core.security import hash_password
from app.main import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        logger = logging.getLogger("hajihaz.app")
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

        self._settings_backup = {
            "database_url": settings.database_url,
            "app_env": settings.app_env,
            "ai_provider": settings.ai_provider,
            "admin_email": settings.admin_email,
            "admin_password": settings.admin_password,
            "admin_password_hash": settings.admin_password_hash,
            "session_ttl_hours": settings.session_ttl_hours,
            "user_session_ttl_hours": settings.user_session_ttl_hours,
            "google_client_id": settings.google_client_id,
            "anthropic_api_key": settings.anthropic_api_key,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
            "online_search_enabled": settings.online_search_enabled,
            "app_log_path_raw": settings.app_log_path_raw,
            "alert_webhook_url": settings.alert_webhook_url,
            "backup_dir_raw": settings.backup_dir_raw,
            "uploads_dir_raw": settings.uploads_dir_raw,
            "public_base_url": settings.public_base_url,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "auth_cookie_secure_raw": settings.auth_cookie_secure_raw,
            "auth_cookie_samesite": settings.auth_cookie_samesite,
            "ocr_enabled": settings.ocr_enabled,
            "alert_email_host": settings.alert_email_host,
            "alert_email_to_raw": settings.alert_email_to_raw,
        }
        self._pbkdf2_iterations_backup = security_module.PBKDF2_ITERATIONS
        security_module.PBKDF2_ITERATIONS = 20_000
        self.temp_dir = tempfile.TemporaryDirectory()
        settings.database_url = f"sqlite:///{Path(self.temp_dir.name) / 'test.db'}"
        settings.app_env = "development"
        settings.app_log_path_raw = str(Path(self.temp_dir.name) / "test.log")
        settings.backup_dir_raw = str(Path(self.temp_dir.name) / "backups")
        settings.uploads_dir_raw = str(Path(self.temp_dir.name) / "uploads")
        settings.public_base_url = "https://example.test"
        settings.rate_limit_enabled = False
        settings.auth_cookie_secure_raw = "false"
        settings.auth_cookie_samesite = "lax"
        settings.ai_provider = "offline"
        settings.admin_email = "admin@hajihaz.local"
        settings.admin_password = "fallback-password"
        settings.admin_password_hash = hash_password("test-password")
        settings.session_ttl_hours = 4
        settings.user_session_ttl_hours = 24
        settings.google_client_id = ""
        settings.anthropic_api_key = ""
        settings.ollama_base_url = ""
        settings.ollama_model = ""
        settings.online_search_enabled = False
        settings.alert_webhook_url = ""
        settings.alert_email_host = ""
        settings.alert_email_to_raw = ""
        settings.ocr_enabled = False
        self.client_ctx = TestClient(create_app())
        self.client = self.client_ctx.__enter__()

    def tearDown(self) -> None:
        self.client_ctx.__exit__(None, None, None)
        self.temp_dir.cleanup()
        logger = logging.getLogger("hajihaz.app")
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        for key, value in self._settings_backup.items():
            setattr(settings, key, value)
        security_module.PBKDF2_ITERATIONS = self._pbkdf2_iterations_backup

    def login(self) -> str:
        response = self.client.post(
            "/auth/login",
            json={"email": settings.admin_email, "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.login()}"}
