from __future__ import annotations

import asyncio
import hashlib
import json
from io import BytesIO
from urllib.parse import quote
from unittest.mock import AsyncMock, patch

from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_user_session
from app.db import get_db
from app.main import create_app
from app.services.ingestion import import_documents_from_url
from app.services.web_lookup import web_lookup_service

from test_support import AppTestCase


class AuthApiTests(AppTestCase):
    def test_production_disables_api_docs_and_adds_security_headers(self) -> None:
        settings.app_env = "production"
        settings.rate_limit_enabled = False
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/redoc").status_code, 404)
            self.assertEqual(client.get("/openapi.json").status_code, 404)

            response = client.get("/health")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("content-security-policy", response.headers)
            self.assertIn("strict-transport-security", response.headers)
            self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")

    def test_user_profile_update_persists_preferences(self) -> None:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO users (google_sub, email, name, email_verified)
                VALUES (?, ?, ?, ?)
                """,
                ("google-user-1", "haji@example.test", "Haji", 1),
            )
            conn.commit()
            user_id = int(conn.execute("SELECT id FROM users WHERE email = ?", ("haji@example.test",)).fetchone()["id"])
        token = create_user_session(user_id)

        response = self.client.patch(
            "/user-auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Haji Haz",
                "username": "Haji Haz!",
                "bio": "Building HajiHaz AI.",
                "ai_nickname": "Haz",
                "personality": "strategic",
                "theme": "light",
                "memory_enabled": False,
                "ai_mode": "reasoning",
                "answer_mode": "detailed",
                "notifications_enabled": True,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["name"], "Haji Haz")
        self.assertEqual(payload["username"], "hajihaz")
        self.assertEqual(payload["bio"], "Building HajiHaz AI.")
        self.assertEqual(payload["ai_nickname"], "Haz")
        self.assertEqual(payload["personality"], "strategic")
        self.assertEqual(payload["theme"], "light")
        self.assertFalse(payload["memory_enabled"])
        self.assertEqual(payload["ai_mode"], "reasoning")
        self.assertEqual(payload["answer_mode"], "detailed")
        self.assertTrue(payload["notifications_enabled"])

    def test_legacy_sha_password_hash_migrates_to_argon2_and_cookie_auth(self) -> None:
        legacy_hash = "sha256:" + hashlib.sha256(b"test-password").hexdigest()
        with get_db() as conn:
            conn.execute(
                "UPDATE admins SET password_hash = ? WHERE email = ?",
                (legacy_hash, "admin@hajihaz.local"),
            )
            conn.commit()

        response = self.client.post(
            "/auth/login",
            json={"email": "admin@hajihaz.local", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("hajihaz_admin_session", response.headers.get("set-cookie", ""))

        cookie_me = self.client.get("/auth/me")
        self.assertEqual(cookie_me.status_code, 200, cookie_me.text)

        with get_db() as conn:
            admin = conn.execute("SELECT password_hash FROM admins WHERE email = ?", ("admin@hajihaz.local",)).fetchone()

        self.assertIsNotNone(admin)
        migrated_hash = str(admin["password_hash"])
        self.assertTrue(migrated_hash.startswith("$argon2id$") or migrated_hash.startswith("pbkdf2_sha256$"))

    def test_login_stores_hashed_session_and_logout_revokes_it(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@hajihaz.local", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        token = payload["token"]

        with get_db() as conn:
            session = conn.execute("SELECT token, email FROM sessions").fetchone()

        self.assertIsNotNone(session)
        self.assertNotEqual(session["token"], token)
        self.assertEqual(len(session["token"]), 64)
        self.assertEqual(session["email"], "admin@hajihaz.local")

        me_response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_response.status_code, 200, me_response.text)

        logout_response = self.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_response.status_code, 200, logout_response.text)
        self.assertEqual(logout_response.json(), {"logged_out": True})

        expired_response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(expired_response.status_code, 401, expired_response.text)

    def test_admin_can_change_own_password_and_add_second_admin(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        users_response = self.client.get("/admin/admin-users", headers=headers)
        self.assertEqual(users_response.status_code, 200, users_response.text)
        self.assertEqual(len(users_response.json()), 1)
        self.assertEqual(users_response.json()[0]["email"], "admin@hajihaz.local")
        self.assertEqual(users_response.json()[0]["is_current"], True)

        create_response = self.client.post(
            "/admin/admin-users",
            headers=headers,
            json={"email": "ops@hajihaz.local", "password": "SecondAdmin123"},
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        self.assertEqual(create_response.json()["email"], "ops@hajihaz.local")

        second_login = self.client.post(
            "/auth/login",
            json={"email": "ops@hajihaz.local", "password": "SecondAdmin123"},
        )
        self.assertEqual(second_login.status_code, 200, second_login.text)
        self.assertEqual(second_login.json()["email"], "ops@hajihaz.local")

        change_response = self.client.post(
            "/auth/change-password",
            headers=headers,
            json={"current_password": "test-password", "new_password": "NewPrimaryPass123"},
        )
        self.assertEqual(change_response.status_code, 200, change_response.text)
        self.assertEqual(change_response.json()["updated"], True)

        old_login = self.client.post(
            "/auth/login",
            json={"email": "admin@hajihaz.local", "password": "test-password"},
        )
        self.assertEqual(old_login.status_code, 401, old_login.text)

        new_login = self.client.post(
            "/auth/login",
            json={"email": "admin@hajihaz.local", "password": "NewPrimaryPass123"},
        )
        self.assertEqual(new_login.status_code, 200, new_login.text)

    def test_user_google_login_claims_guest_conversation_and_keeps_admin_auth_separate(self) -> None:
        settings.google_client_id = "google-client-id.apps.googleusercontent.com"

        guest_chat = self.client.post("/chat", json={"message": "hello macha"})
        self.assertEqual(guest_chat.status_code, 200, guest_chat.text)
        guest_payload = guest_chat.json()
        self.assertTrue(guest_payload["session_id"])

        config_response = self.client.get("/user-auth/config")
        self.assertEqual(config_response.status_code, 200, config_response.text)
        self.assertEqual(
            config_response.json(),
            {
                "enabled": True,
                "client_id": "google-client-id.apps.googleusercontent.com",
                "guest_mode": True,
            },
        )

        with patch(
            "app.routes.user_auth.verify_google_credential",
            return_value={
                "google_sub": "google-user-123",
                "email": "user@example.com",
                "name": "Haji User",
                "picture_url": "https://example.com/avatar.png",
                "email_verified": True,
            },
        ):
            login_response = self.client.post(
                "/user-auth/google",
                json={"credential": "x" * 30, "session_id": guest_payload["session_id"]},
            )

        self.assertEqual(login_response.status_code, 200, login_response.text)
        login_payload = login_response.json()
        self.assertEqual(login_payload["claimed_session_id"], guest_payload["session_id"])
        self.assertTrue(login_payload["token"])
        self.assertEqual(login_payload["user"]["email"], "user@example.com")

        user_headers = {"Authorization": f"Bearer {login_payload['token']}"}
        me_response = self.client.get("/user-auth/me", headers=user_headers)
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["email"], "user@example.com")

        sessions_response = self.client.get("/chat/sessions", headers=user_headers)
        self.assertEqual(sessions_response.status_code, 200, sessions_response.text)
        session_ids = [item["id"] for item in sessions_response.json()]
        self.assertIn(guest_payload["session_id"], session_ids)

        owned_session = self.client.get(f"/chat/session/{guest_payload['session_id']}", headers=user_headers)
        self.assertEqual(owned_session.status_code, 200, owned_session.text)
        self.assertEqual(owned_session.json()["session"]["id"], guest_payload["session_id"])

        self.client.cookies.clear()
        anonymous_access = self.client.get(f"/chat/session/{guest_payload['session_id']}")
        self.assertEqual(anonymous_access.status_code, 404, anonymous_access.text)

        admin_access = self.client.post(
            "/auth/login",
            json={"email": "admin@hajihaz.local", "password": "test-password"},
        )
        self.assertEqual(admin_access.status_code, 200, admin_access.text)

    def test_user_auth_config_is_disabled_without_google_client_id(self) -> None:
        settings.google_client_id = ""

        response = self.client.get("/user-auth/config")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"enabled": False, "client_id": None, "guest_mode": True})


class AdminDocumentApiTests(AppTestCase):
    def test_document_core_persona_flag_can_be_created_and_toggled(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        create_response = self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji identity profile",
                "content": "Haji is the founder voice behind HajiHaz AI and this document should lead owner-profile answers.",
                "tags": ["haji", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        created_payload = create_response.json()
        self.assertTrue(created_payload["core_persona"])

        document_id = created_payload["id"]
        toggle_response = self.client.post(
            f"/admin/documents/{document_id}/core-persona",
            headers=headers,
            json={"core_persona": False},
        )
        self.assertEqual(toggle_response.status_code, 200, toggle_response.text)
        self.assertFalse(toggle_response.json()["core_persona"])

        listing_response = self.client.get("/admin/documents", headers=headers)
        self.assertEqual(listing_response.status_code, 200, listing_response.text)
        listed_document = next(item for item in listing_response.json() if item["id"] == document_id)
        self.assertFalse(listed_document["core_persona"])

    def test_chat_recovers_session_history_for_follow_up_without_frontend_history(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        create_response = self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Father Name: Syed Mohamed Hussain Sahib "
                    "Nickname: Kannadi Sabu "
                    "Role: Head of the family "
                    "Contribution: Provides guidance and foundational support "
                    "Relationship with Haji: Father"
                ),
                "tags": ["haji", "family", "father"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)

        first_chat = self.client.post("/chat", json={"message": "who is haji father"})
        self.assertEqual(first_chat.status_code, 200, first_chat.text)
        first_payload = first_chat.json()
        self.assertIn("Syed Mohamed Hussain Sahib", first_payload["answer"])

        second_chat = self.client.post(
            "/chat",
            json={
                "message": "give details of him",
                "session_id": first_payload["session_id"],
                "history": [],
            },
        )
        self.assertEqual(second_chat.status_code, 200, second_chat.text)
        second_payload = second_chat.json()
        self.assertIn("Syed Mohamed Hussain Sahib is Haji's father.", second_payload["answer"])
        self.assertIn("He is head of the family.", second_payload["answer"])

    def test_bulk_import_update_and_delete_document(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        baseline = self.client.get("/admin/stats", headers=headers).json()["documents"]

        import_response = self.client.post(
            "/admin/documents/import",
            headers=headers,
            json={
                "skip_duplicates": True,
                "documents": [
                    {
                        "title": "Import alpha",
                        "content": "Bulk import alpha content for operations and pricing workflow decisions.",
                        "tags": ["alpha", "bulk"],
                        "source": "upload",
                    },
                    {
                        "title": "Import beta",
                        "content": "Bulk import beta content for support and client follow-up workflow decisions.",
                        "tags": ["beta", "bulk"],
                        "source": "upload",
                    },
                    {
                        "title": "Import alpha",
                        "content": "Bulk import alpha content for operations and pricing workflow decisions.",
                        "tags": ["duplicate"],
                        "source": "upload",
                    },
                ],
            },
        )
        self.assertEqual(import_response.status_code, 200, import_response.text)
        imported_payload = import_response.json()
        self.assertEqual(imported_payload["imported"], 2)
        self.assertEqual(imported_payload["skipped"], 1)

        document_id = imported_payload["documents"][0]["id"]
        update_response = self.client.put(
            f"/admin/documents/{document_id}",
            headers=headers,
            json={
                "title": "Import alpha updated",
                "content": "Updated import alpha content for operations and pricing workflow decisions.",
                "tags": ["alpha", "updated"],
                "source": "upload",
            },
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        self.assertEqual(update_response.json()["title"], "Import alpha updated")

        delete_response = self.client.delete(f"/admin/documents/{document_id}", headers=headers)
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertEqual(delete_response.json()["deleted"], True)

        stats_response = self.client.get("/admin/stats", headers=headers)
        self.assertEqual(stats_response.status_code, 200, stats_response.text)
        final_documents = stats_response.json()["documents"]
        self.assertEqual(final_documents, baseline + 1)
        self.assertIn("web_search_enabled", stats_response.json())
        self.assertIn("active_sources", stats_response.json())

    def test_file_import_route_supports_text_and_docx(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        docx_buffer = BytesIO()
        document = DocxDocument()
        document.add_paragraph("DOCX upload content for client onboarding and support workflow guidance.")
        document.save(docx_buffer)
        docx_buffer.seek(0)

        response = self.client.post(
            "/admin/documents/import/files",
            headers=headers,
            data={"group_name": "Operations", "tags_csv": "onboarding, uploads", "skip_duplicates": "true"},
            files=[
                ("files", ("playbook.txt", b"Text upload content for pricing FAQ and SOP guidance.", "text/plain")),
                (
                    "files",
                    (
                        "workflow.docx",
                        docx_buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                ),
            ],
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["imported"], 2)
        self.assertTrue(all(document["group_name"] == "Operations" for document in payload["documents"]))
        self.assertTrue(any(document["source"].startswith("upload:docx") for document in payload["documents"]))

    def test_url_import_export_and_debug_routes(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        with patch(
            "app.routes.admin.import_documents_from_url",
            AsyncMock(
                return_value=[
                    {
                        "title": "Imported website",
                        "content": "Imported website content for broader market context and competitor notes.",
                        "tags": ["market"],
                        "source": "url",
                        "group_name": "Research",
                        "source_url": "https://example.com/market",
                    }
                ]
            ),
        ):
            import_response = self.client.post(
                "/admin/documents/import/url",
                headers=headers,
                json={"url": "https://example.com/market", "group_name": "Research", "tags": ["market"]},
            )

        self.assertEqual(import_response.status_code, 200, import_response.text)
        self.assertEqual(import_response.json()["imported"], 1)

        export_response = self.client.get("/admin/documents/export?export_format=json", headers=headers)
        self.assertEqual(export_response.status_code, 200, export_response.text)
        self.assertEqual(export_response.headers["content-type"].split(";")[0], "application/json")
        self.assertIn("attachment;", export_response.headers["content-disposition"])
        self.assertIn("Imported website", export_response.text)

        debug_response = self.client.get("/admin/debug", headers=headers)
        self.assertEqual(debug_response.status_code, 200, debug_response.text)
        debug_payload = debug_response.json()
        self.assertGreaterEqual(debug_payload["uptime_seconds"], 0)
        self.assertTrue(debug_payload["source_health"])
        self.assertTrue(debug_payload["recent_health_checks"])
        self.assertTrue(debug_payload["recent_logs"])
        self.assertIn("resource_metrics", debug_payload)
        self.assertIn("backups", debug_payload)
        self.assertIn("analytics", debug_payload)
        self.assertIn("secret_audit", debug_payload)

    def test_runtime_pulse_requires_admin_login(self) -> None:
        unauthenticated = self.client.get("/admin/runtime-pulse")
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)
        headers = {"Authorization": f"Bearer {self.login()}"}
        with patch(
            "app.routes.admin.ai_service.runtime_pulse",
            return_value={
                "provider": "ollama",
                "provider_label": "Ollama + web",
                "status": "degraded",
                "status_label": "Degraded",
                "reason": "Ollama probe failed: ConnectError. The assistant can still fall back to web-backed answers.",
                "checked_at": "2026-04-24T10:00:00+00:00",
                "uptime_seconds": 120,
            },
        ):
            response = self.client.get("/admin/runtime-pulse", headers=headers)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {
                "provider": "ollama",
                "provider_label": "Ollama + web",
                "status": "degraded",
                "status_label": "Degraded",
                "reason": "Ollama probe failed: ConnectError. The assistant can still fall back to web-backed answers.",
                "checked_at": "2026-04-24T10:00:00+00:00",
                "uptime_seconds": 120,
            },
        )

    def test_source_controls_and_backup_routes(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        create_response = self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Syncable page",
                "content": "Initial content for a syncable source.",
                "tags": ["sync"],
                "source": "url",
                "group_name": "Research",
                "source_url": "https://example.com/source",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)

        sources_response = self.client.get("/admin/sources", headers=headers)
        self.assertEqual(sources_response.status_code, 200, sources_response.text)
        sources = sources_response.json()
        self.assertTrue(sources)
        target_source = next(item for item in sources if item.get("source_url") == "https://example.com/source")
        source_key = quote(target_source["source_key"], safe="")
        self.assertTrue(target_source["enabled"])

        disable_response = self.client.post(f"/admin/sources/{source_key}/disable", headers=headers)
        self.assertEqual(disable_response.status_code, 200, disable_response.text)
        self.assertFalse(disable_response.json()["source"]["enabled"])

        enable_response = self.client.post(f"/admin/sources/{source_key}/enable", headers=headers)
        self.assertEqual(enable_response.status_code, 200, enable_response.text)
        self.assertTrue(enable_response.json()["source"]["enabled"])

        reindex_response = self.client.post(f"/admin/sources/{source_key}/reindex", headers=headers)
        self.assertEqual(reindex_response.status_code, 200, reindex_response.text)
        self.assertEqual(reindex_response.json()["action"], "reindexed")

        with patch(
            "app.services.ingestion.import_documents_from_url",
            AsyncMock(
                return_value=[
                    {
                        "title": "Syncable page",
                        "content": "Fresh synced content from the original source.",
                        "tags": ["sync"],
                        "source": "url",
                        "group_name": "Research",
                        "source_url": "https://example.com/source",
                    }
                ]
            ),
        ):
            sync_response = self.client.post(f"/admin/sources/{source_key}/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 200, sync_response.text)
        self.assertEqual(sync_response.json()["action"], "synced")

        backup_response = self.client.post(
            "/admin/backups/create",
            headers=headers,
            json={"note": "test backup"},
        )
        self.assertEqual(backup_response.status_code, 200, backup_response.text)
        backup_id = backup_response.json()["id"]
        self.assertTrue(backup_response.json()["download_ready"])

        list_backups_response = self.client.get("/admin/backups", headers=headers)
        self.assertEqual(list_backups_response.status_code, 200, list_backups_response.text)
        self.assertTrue(list_backups_response.json())

        download_response = self.client.get(f"/admin/backups/{backup_id}/download", headers=headers)
        self.assertEqual(download_response.status_code, 200, download_response.text)
        self.assertEqual(download_response.headers["content-type"], "application/zip")

        analytics_response = self.client.get("/admin/analytics", headers=headers)
        self.assertEqual(analytics_response.status_code, 200, analytics_response.text)
        self.assertIn("total_requests", analytics_response.json())

        maintenance_response = self.client.post("/admin/maintenance", headers=headers)
        self.assertEqual(maintenance_response.status_code, 200, maintenance_response.text)
        self.assertIn("metrics", maintenance_response.json())

    def test_public_google_doc_import_and_image_ocr_support(self) -> None:
        class FakeResponse:
            def __init__(self, *, text: str = "", content: bytes = b"", headers: dict | None = None) -> None:
                self.text = text
                self.content = content
                self.headers = headers or {}

            def raise_for_status(self) -> None:
                return None

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url: str, headers: dict | None = None):
                if "document" in url and "export?format=txt" in url:
                    return FakeResponse(content=b"Google doc text for public knowledge import.", headers={"content-type": "text/plain"})
                return FakeResponse(text="<html><title>Fallback</title><body><p>Fallback text.</p></body></html>", headers={"content-type": "text/html"})

        with patch("app.services.ingestion.httpx.AsyncClient", FakeAsyncClient):
            documents = asyncio.run(
                import_documents_from_url(
                    "https://docs.google.com/document/d/abc123/edit",
                    "Research",
                    ["public"],
                )
            )

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["source"], "google-docs")
        self.assertEqual(documents[0]["group_name"], "Research")
        self.assertIn("public", documents[0]["tags"])

        settings.ocr_enabled = True
        headers = {"Authorization": f"Bearer {self.login()}"}
        with patch("app.services.ingestion._ocr_command_available", return_value=True), patch(
            "app.services.ingestion.subprocess.run"
        ) as mocked_run:
            mocked_run.return_value.stdout = "Scanned image text recovered with OCR."
            response = self.client.post(
                "/admin/documents/import/files",
                headers=headers,
                data={"group_name": "Scans", "tags_csv": "ocr"},
                files=[("files", ("scan.png", b"fake-image-bytes", "image/png"))],
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["imported"], 1)
        self.assertTrue(mocked_run.called)

    def test_url_import_rejects_internal_and_unsupported_urls(self) -> None:
        with self.assertRaises(ValueError):
            asyncio.run(import_documents_from_url("http://127.0.0.1/private"))
        with self.assertRaises(ValueError):
            asyncio.run(import_documents_from_url("ftp://example.com/file.txt"))


class ChatApiTests(AppTestCase):
    def test_chat_returns_notice_separate_from_answer(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Pricing guide",
                "content": "Starter pricing begins with a discovery call and a clearly scoped proposal before quoting.",
                "tags": ["pricing"],
                "source": "manual",
            },
        )

        response = self.client.post("/chat", json={"message": "How does pricing start?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["answer"])
        self.assertTrue(payload["notice"])
        self.assertNotIn("AI provider is set to offline mode", payload["answer"])

    def test_chat_prefers_persona_profile_knowledge_for_haji_identity_question(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji profile",
                "content": (
                    "Haji is the founder behind HajiHaz AI and is described in the knowledge base as a practical, "
                    "business-focused operator whose assistant should reflect his communication style and decision-making approach."
                ),
                "tags": ["haji", "profile", "identity"],
                "source": "manual",
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Haji Wright",
                        "excerpt": "Haji Amir Wright is an American professional soccer player.",
                        "url": "https://example.com/haji-wright",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "Who is Haji?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Haji", payload["answer"])
        self.assertNotIn("soccer", payload["answer"].lower())
        self.assertFalse(any(citation["kind"] == "web" for citation in payload["citations"]))
        mocked_search.assert_not_awaited()

    def test_chat_prefers_persona_business_question_locally(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji business portfolio",
                "content": (
                    "Haji currently owns and operates Suplaykart and is also involved in advisory, planning, and business systems work through HajiHaz AI."
                ),
                "tags": ["haji", "business", "portfolio", "suplaykart"],
                "source": "manual",
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Generic business owner article",
                        "excerpt": "A business owner manages one or more companies.",
                        "url": "https://example.com/business-owner",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "What businesses does Haji own?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Suplaykart", payload["answer"])
        self.assertFalse(any(citation["kind"] == "web" for citation in payload["citations"]))
        mocked_search.assert_not_awaited()

    def test_chat_uses_recent_history_for_persona_follow_up(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji profile",
                "content": "Haji is the founder behind HajiHaz AI and leads its business direction.",
                "tags": ["haji", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji education",
                "content": "Haji holds a business-focused academic background and relevant qualifications in technology and operations.",
                "tags": ["haji", "education", "qualifications"],
                "source": "manual",
                "core_persona": True,
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(return_value=[]),
        ) as mocked_search:
            response = self.client.post(
                "/chat",
                json={
                    "message": "And what about his education?",
                    "history": [
                        {"role": "user", "content": "Who is Haji?"},
                        {"role": "assistant", "content": "Haji is the founder behind HajiHaz AI."},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("education", payload["answer"].lower())
        self.assertIn("qualification", payload["answer"].lower())
        self.assertFalse(any(citation["kind"] == "web" for citation in payload["citations"]))
        mocked_search.assert_not_awaited()

    def test_chat_prioritizes_core_persona_document_for_identity_prompt(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "General note",
                "content": "Haji is connected to general business systems and operations work.",
                "tags": ["haji", "operations"],
                "source": "manual",
                "core_persona": False,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Core Haji profile",
                "content": (
                    "Haji is Syed Hasan Kuddos Sahib, the founder behind HajiHaz AI, and the assistant should represent "
                    "his voice, business direction, and working style."
                ),
                "tags": ["haji", "profile", "identity"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post("/chat", json={"message": "Who is Haji?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertTrue(payload["citations"])
        self.assertEqual(payload["citations"][0]["title"], "Core Haji profile")
        self.assertIn("Syed Hasan Kuddos Sahib", payload["answer"])

    def test_chat_does_not_hallucinate_missing_persona_relationship_detail(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Core Haji profile",
                "content": (
                    "Haji is Syed Hasan Kuddos Sahib, the founder behind HajiHaz AI, and the assistant should reflect "
                    "his voice, business direction, and working style."
                ),
                "tags": ["haji", "profile", "identity"],
                "source": "manual",
                "core_persona": True,
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Generic friendship article",
                        "excerpt": "A friend is a person with whom one has a bond of mutual affection.",
                        "url": "https://example.com/friend",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "who is haji friend"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("don't know", payload["answer"].lower())
        self.assertFalse(payload["citations"])
        self.assertIn("not present in haji's saved knowledge", (payload["notice"] or "").lower())
        mocked_search.assert_not_awaited()

    def test_chat_answers_simple_persona_relationship_prompt_with_direct_fact(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Mother Name: Shehnaaz Nisha Role: - Primary financial supporter (early-stage investor in Haji's business journey) "
                    "Contribution: - Invested capital into Haji's business (Suplaykart) - Provides emotional and family support. "
                    "Father Name: Syed Mohamed Hussain Sahib Nickname: Kannadai Sabu Role: - Head of the family."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post("/chat", json={"message": "who is haji mother"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Shehnaaz Nisha is Haji's mother.", payload["answer"])
        self.assertNotIn("Father Name", payload["answer"])
        self.assertNotIn("Primary financial supporter", payload["answer"])

    def test_chat_prefers_local_family_knowledge_for_known_name_query(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Mother Name: Shehnaaz Nisha Role: - Primary financial supporter (early-stage investor in Haji's business journey) "
                    "Contribution: - Invested capital into Haji's business (Suplaykart) - Provides emotional and family support. "
                    "Relationship with Haji: - Mother - Strong support system in both personal and business aspects."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Shehnaaz Gill",
                        "excerpt": "Shehnaaz Gill is an Indian actress, model and singer.",
                        "url": "https://example.com/shehnaaz-gill",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "who is shehnaaz"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Shehnaaz Nisha is Haji's mother.", payload["answer"])
        self.assertFalse(any(citation.get("kind") == "web" for citation in payload["citations"]))
        self.assertFalse(payload["notice"])
        mocked_search.assert_not_awaited()

    def test_chat_prefers_local_extended_family_knowledge_for_known_name_query(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Grandfather (Maternal) Name: Syed Meeran Sahib Nickname: Sinna Kamil Sahib "
                    "Relationship: Mother's father Details: A respected elder in the family. "
                    "Influence: Part of Haji's family heritage and background."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Syed Meeran",
                        "excerpt": "A public figure unrelated to Haji.",
                        "url": "https://example.com/syed-meeran",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "who is syed meeran"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Syed Meeran Sahib is Haji's maternal grandfather.", payload["answer"])
        self.assertNotIn("family structure", payload["answer"].lower())
        self.assertFalse(any(citation.get("kind") == "web" for citation in payload["citations"]))
        mocked_search.assert_not_awaited()

    def test_chat_uses_recent_history_for_known_family_entity_follow_up(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Mother Name: Shehnaaz Nisha Role: - Primary financial supporter (early-stage investor in Haji's business journey) "
                    "Contribution: - Invested capital into Haji's business (Suplaykart) - Provides emotional and family support. "
                    "Relationship with Haji: - Mother - Strong support system in both personal and business aspects."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji AI Personality & Response System",
                "content": (
                    "AI Behavior Rules - Use stored knowledge about Haji first - Then enhance with general knowledge "
                    "- Do not hallucinate personal facts."
                ),
                "tags": ["haji", "system", "personality"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post(
            "/chat",
            json={
                "message": "give more details of her",
                "history": [
                    {"role": "user", "content": "who is shehnaaz"},
                    {"role": "assistant", "content": "Shehnaaz Nisha is Haji's mother."},
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Shehnaaz Nisha", payload["answer"])
        self.assertIn("mother", payload["answer"].lower())
        self.assertNotIn("don't know", payload["answer"].lower())
        self.assertIn("primary financial supporter", payload["answer"].lower())
        self.assertNotIn("ai behavior rules", payload["answer"].lower())
        self.assertNotIn("do not hallucinate", payload["answer"].lower())

    def test_chat_uses_recent_history_for_known_male_family_entity_follow_up(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Father Name: Syed Mohamed Hussain Sahib Nickname: Kannadai Sabu "
                    "Role: - Head of the family - Provides guidance and foundational support "
                    "Relationship with Haji: - Father - Acts as a senior figure in decision-making and life direction."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji AI Personality & Response System",
                "content": "AI Behavior Rules - Use stored knowledge about Haji first - Then enhance with general knowledge.",
                "tags": ["haji", "system", "personality"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post(
            "/chat",
            json={
                "message": "give details of him",
                "history": [
                    {"role": "user", "content": "who is hussain"},
                    {"role": "assistant", "content": "Syed Mohamed Hussain Sahib is Haji's father."},
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Syed Mohamed Hussain Sahib", payload["answer"])
        self.assertIn("father", payload["answer"].lower())
        self.assertIn("He is", payload["answer"])
        self.assertNotIn("She is", payload["answer"])
        self.assertNotIn("death and other details", payload["answer"].lower())
        self.assertNotIn("don't know", payload["answer"].lower())

    def test_chat_uses_recent_history_for_extended_family_entity_follow_up(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Grandfather (Maternal) Name: Syed Meeran Sahib Nickname: Sinna Kamil Sahib "
                    "Relationship: Mother's father Details: A respected elder in the family. "
                    "Influence: Part of Haji's family heritage and background."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji AI Personality & Response System",
                "content": "AI Behavior Rules - Use stored knowledge about Haji first - Then enhance with general knowledge.",
                "tags": ["haji", "system", "personality"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post(
            "/chat",
            json={
                "message": "give more details of him",
                "history": [
                    {"role": "user", "content": "who is syed meeran"},
                    {"role": "assistant", "content": "Syed Meeran Sahib is Haji's maternal grandfather."},
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Syed Meeran Sahib", payload["answer"])
        self.assertIn("maternal grandfather", payload["answer"].lower())
        self.assertIn("He", payload["answer"])
        self.assertIn("respected elder", payload["answer"].lower())
        self.assertIn("family heritage", payload["answer"].lower())
        self.assertNotIn("ai behavior rules", payload["answer"].lower())
        self.assertNotIn("don't know", payload["answer"].lower())

    def test_chat_uses_recent_history_for_bare_extended_family_detail_follow_up(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Grandfather (Maternal) Name: Syed Meeran Sahib Nickname: Sinna Kamil Sahib "
                    "Relationship: Mother's father Details: A respected elder in the family. "
                    "Influence: Part of Haji's family heritage and background."
                ),
                "tags": ["haji", "family", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji AI Personality & Response System",
                "content": "AI Behavior Rules - Use stored knowledge about Haji first - Then enhance with general knowledge.",
                "tags": ["haji", "system", "personality"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post(
            "/chat",
            json={
                "message": "more details",
                "history": [
                    {"role": "user", "content": "who is syed meeran"},
                    {"role": "assistant", "content": "Syed Meeran Sahib is Haji's maternal grandfather."},
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("Syed Meeran Sahib", payload["answer"])
        self.assertIn("maternal grandfather", payload["answer"].lower())
        self.assertIn("He", payload["answer"])
        self.assertIn("respected elder", payload["answer"].lower())
        self.assertIn("family heritage", payload["answer"].lower())
        self.assertNotIn("ai behavior rules", payload["answer"].lower())
        self.assertNotIn("don't know", payload["answer"].lower())

    def test_chat_handles_casual_checkin_without_web_lookup(self) -> None:
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Macha mythology",
                        "excerpt": "Macha is a figure from Irish mythology.",
                        "url": "https://example.com/macha",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "how are you macha"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "conversation")
        self.assertFalse(payload["citations"])
        self.assertFalse(payload["notice"])
        self.assertIn("doing well", payload["answer"].lower())
        self.assertIn("help", payload["answer"].lower())
        mocked_search.assert_not_awaited()

    def test_chat_handles_simple_greeting_without_web_lookup(self) -> None:
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(return_value=[]),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "hello macha"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "conversation")
        self.assertFalse(payload["citations"])
        self.assertIn("ready", payload["answer"].lower())
        mocked_search.assert_not_awaited()

    def test_chat_supports_founder_tone_for_conversation(self) -> None:
        settings.online_search_enabled = True

        response = self.client.post(
            "/chat",
            json={"message": "hello macha", "answer_mode": "founder"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "conversation")
        self.assertIn("practical", payload["answer"].lower())

    def test_chat_uses_web_fallback_for_generic_question(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Business capital notes",
                "content": "Our mother invested capital into the business during the early stage.",
                "tags": ["finance"],
                "source": "manual",
            },
        )
        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Closed-ended question",
                        "excerpt": "A closed-ended question requires a participant to choose from prepared responses.",
                        "url": "https://example.com/closed-question",
                        "kind": "web",
                        "source": "Web",
                    },
                    {
                        "title": "France",
                        "excerpt": "Paris is the capital and largest city of France.",
                        "url": "https://example.com/france",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ):
            response = self.client.post("/chat", json={"message": "What is the capital of France?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "web")
        self.assertTrue(payload["notice"])
        self.assertTrue(payload["citations"])
        self.assertEqual(payload["citations"][0]["kind"], "web")
        self.assertEqual(payload["citations"][0]["title"], "France")
        self.assertIn("Paris", payload["answer"])
        self.assertIn("capital", payload["answer"].lower())
        self.assertNotIn("Here’s the short answer", payload["answer"])
        self.assertNotIn("Why that answer is likely right", payload["answer"])
        self.assertNotIn("\n-", payload["answer"])
        self.assertEqual(payload["answer"].count("\n"), 0)

    def test_chat_does_not_use_saved_profile_for_current_affairs(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "RAJA MANICKAM",
                "content": (
                    "PERSON PROFILE: RAJA MANICKAM Full Name: Raja Manickam. "
                    "Location: Nagore, Tamil Nadu. Raja Manickam works at the Nagore Dargah office."
                ),
                "tags": ["profile", "family", "haji"],
                "source": "manual",
                "core_persona": True,
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Prime Minister of India",
                        "excerpt": "Narendra Modi is the current Prime Minister of India.",
                        "url": "https://example.com/india-prime-minister",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "Who is the Prime Minister of India?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "current_affairs")
        self.assertEqual(payload["source_strategy"], "web")
        self.assertEqual(payload["mode"], "web")
        self.assertIn("Narendra Modi", payload["answer"])
        self.assertNotIn("RAJA MANICKAM", payload["answer"])
        self.assertFalse(any(citation["title"] == "RAJA MANICKAM" for citation in payload["citations"]))
        self.assertTrue(all(citation["kind"] == "web" for citation in payload["citations"]))
        mocked_search.assert_awaited_once()

    def test_chat_uses_saved_memory_for_user_relationship_question(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Family Structure",
                "content": (
                    "Father Name: Syed Mohamed Hussain Sahib Nickname: Kannadai Sabu "
                    "Relationship with Haji: Father. Role: Head of the family."
                ),
                "tags": ["haji", "family", "father"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post("/chat", json={"message": "Who is my father?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "personal_memory")
        self.assertEqual(payload["source_strategy"], "memory")
        self.assertEqual(payload["mode"], "knowledge")
        self.assertGreater(payload["memory_confidence"], 0)
        self.assertIn("Syed Mohamed Hussain Sahib", payload["answer"])
        self.assertTrue(payload["citations"])

    def test_chat_supports_concise_mode_for_web_answers(self) -> None:
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "France",
                        "excerpt": "Paris is the capital and largest city of France. It is a major European centre for culture, business, and diplomacy.",
                        "url": "https://example.com/france",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ):
            response = self.client.post(
                "/chat",
                json={"message": "What is the capital of France?", "answer_mode": "concise"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "web")
        self.assertIn("Paris", payload["answer"])
        self.assertNotIn("major European centre", payload["answer"])
        self.assertEqual(payload["citations"][0]["title"], "France")

    def test_chat_prefers_web_for_broad_generic_question_with_only_weak_local_context(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "General strategy note",
                "content": "Our internal strategy document talks about execution discipline and weekly reviews.",
                "tags": ["strategy"],
                "source": "manual",
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Business strategy",
                        "excerpt": "A business strategy explains how a company creates value and wins in its market.",
                        "url": "https://example.com/business-strategy",
                        "kind": "web",
                        "source": "Web",
                    },
                    {
                        "title": "WhatsApp",
                        "excerpt": "In January 2018, WhatsApp released a standalone business app called WhatsApp Business.",
                        "url": "https://example.com/whatsapp",
                        "kind": "web",
                        "source": "Web",
                    },
                    {
                        "title": "Strategic management",
                        "excerpt": "Strategic management involves the formulation and implementation of the major goals and initiatives taken by an organization's managers.",
                        "url": "https://example.com/strategic-management",
                        "kind": "web",
                        "source": "Web",
                    },
                ]
            ),
        ):
            response = self.client.post("/chat", json={"message": "What is business strategy?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "web")
        self.assertTrue(any(citation["kind"] == "web" for citation in payload["citations"]))
        self.assertEqual(payload["citations"][0]["title"], "Business strategy")
        self.assertNotIn("WhatsApp", payload["answer"])
        self.assertIn("live web context", payload["notice"])
        self.assertIn("strategy", payload["answer"].lower())
        self.assertNotIn("Here’s the short answer", payload["answer"])
        self.assertNotIn("Why that answer is likely right", payload["answer"])
        self.assertNotIn("\n-", payload["answer"])

    def test_chat_keeps_internal_upload_question_grounded_locally(self) -> None:
        settings.online_search_enabled = True
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Upload priorities",
                "content": "Upload pricing FAQs, SOPs, and real client workflow examples before anything else.",
                "tags": ["rag", "uploads"],
                "source": "manual",
            },
        )

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Generic blog",
                        "excerpt": "Upload random long-form content without structure.",
                        "url": "https://example.com/generic",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ) as mocked_search:
            response = self.client.post("/chat", json={"message": "What should I upload next to improve the RAG answers?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertFalse(payload["notice"])
        self.assertFalse(any(citation["kind"] == "web" for citation in payload["citations"]))
        mocked_search.assert_not_awaited()

    def test_chat_formats_non_persona_knowledge_answers_cleanly(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Client onboarding guide",
                "content": (
                    "Client onboarding starts with a discovery call, then a scoped proposal, and then a kickoff checklist "
                    "so the team can move into delivery with clear ownership."
                ),
                "tags": ["onboarding", "operations"],
                "source": "manual",
            },
        )

        response = self.client.post("/chat", json={"message": "How does client onboarding start?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("discovery call", payload["answer"].lower())
        self.assertNotIn("Here’s the short answer", payload["answer"])
        self.assertNotIn("Why that fits your library", payload["answer"])
        self.assertNotIn("\n-", payload["answer"])

    def test_chat_summarizes_bullet_knowledge_into_natural_answer(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Client onboarding checklist",
                "content": (
                    "- Client onboarding starts with a discovery call\n"
                    "- Then a scoped proposal is shared\n"
                    "- Then a kickoff checklist sets ownership before delivery"
                ),
                "tags": ["onboarding", "operations"],
                "source": "manual",
            },
        )

        response = self.client.post("/chat", json={"message": "How does client onboarding start?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("client onboarding starts with", payload["answer"].lower())
        self.assertIn("discovery call", payload["answer"].lower())
        self.assertIn("scoped proposal", payload["answer"].lower())
        self.assertNotIn("\n-", payload["answer"])
        self.assertNotIn("the key points are", payload["answer"].lower())

    def test_chat_summarizes_inline_bullet_knowledge_without_leaking_formatting(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Client onboarding playbook",
                "content": (
                    "Client onboarding starts with: - Discovery call - Scoped proposal - Kickoff checklist "
                    "--- 2. Delivery starts once ownership is clear."
                ),
                "tags": ["onboarding", "operations"],
                "source": "manual",
            },
        )

        response = self.client.post("/chat", json={"message": "How does client onboarding start?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("client onboarding starts with", payload["answer"].lower())
        self.assertIn("discovery call", payload["answer"].lower())
        self.assertIn("kickoff checklist", payload["answer"].lower())
        self.assertNotIn(" - ", payload["answer"])
        self.assertNotIn("---", payload["answer"])
        self.assertNotIn("2.", payload["answer"])

    def test_chat_prefers_operational_knowledge_over_persona_note_for_operational_prompt(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Cognitive System",
                "content": (
                    "Key principles: - Start first, refine later - Execution creates clarity - Speed is an advantage. "
                    "He avoids waiting for perfect knowledge."
                ),
                "tags": ["haji", "system"],
                "source": "manual",
                "core_persona": True,
            },
        )
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Client onboarding checklist",
                "content": (
                    "- Client onboarding starts with a discovery call\n"
                    "- Then a scoped proposal is shared\n"
                    "- Then a kickoff checklist sets ownership before delivery"
                ),
                "tags": ["onboarding", "operations", "client"],
                "source": "manual",
            },
        )

        response = self.client.post("/chat", json={"message": "How does client onboarding start?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "knowledge")
        self.assertIn("discovery call", payload["answer"].lower())
        self.assertIn("scoped proposal", payload["answer"].lower())
        self.assertNotIn("execution creates clarity", payload["answer"].lower())
        self.assertTrue(payload["citations"])
        self.assertEqual(payload["citations"][0]["title"], "Client onboarding checklist")

    def test_chat_does_not_use_persona_note_as_fake_operational_answer(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji Cognitive System",
                "content": (
                    "Key principles: - Start first, refine later - Execution creates clarity - Speed is an advantage. "
                    "He avoids waiting for perfect knowledge."
                ),
                "tags": ["haji", "system"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post("/chat", json={"message": "How does client onboarding start?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertNotIn("execution creates clarity", payload["answer"].lower())
        self.assertNotIn("speed is an advantage", payload["answer"].lower())
        self.assertFalse(any(citation["title"] == "Haji Cognitive System" for citation in payload["citations"]))

    def test_chat_uses_ollama_with_web_context_for_generic_question(self) -> None:
        settings.ai_provider = "ollama"
        settings.online_search_enabled = True
        settings.ollama_base_url = "http://ollama.test/api"
        settings.ollama_model = "qwen3:0.6b"

        captured_payload = {}

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "message": {
                        "content": (
                            "Paris is the capital of France, as of my knowledge cutoff date on [insert date].\n"
                            "--- Reasoning:\n- This came from web evidence."
                        )
                    }
                }

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url: str, json: dict):
                captured_payload["url"] = url
                captured_payload["json"] = json
                return FakeResponse()

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "France",
                        "excerpt": "Paris is the capital and largest city of France.",
                        "url": "https://example.com/france",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ), patch("app.services.anthropic_client.httpx.AsyncClient", FakeAsyncClient):
            response = self.client.post("/chat", json={"message": "What is the capital of France?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "ollama")
        self.assertIn("Ollama", payload["notice"])
        self.assertTrue(any(citation["kind"] == "web" for citation in payload["citations"]))
        self.assertEqual(captured_payload["url"], "http://ollama.test/api/chat")
        self.assertIn("Web evidence", captured_payload["json"]["messages"][1]["content"])
        self.assertIn("France", payload["answer"])
        self.assertNotIn("[insert date]", payload["answer"])
        self.assertNotIn("knowledge cutoff", payload["answer"].lower())
        self.assertNotIn("reasoning", payload["answer"].lower())

    def test_chat_simplifies_current_office_model_answer(self) -> None:
        settings.ai_provider = "ollama"
        settings.online_search_enabled = True
        settings.ollama_base_url = "http://ollama.test/api"
        settings.ollama_model = "qwen3:0.6b"

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "message": {
                        "content": (
                            "The Prime Minister of India currently serves as Narendra Modi. "
                            "He was sworn into office on May 26, 2017."
                        )
                    }
                }

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url: str, json: dict):
                return FakeResponse()

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Prime Minister of India",
                        "excerpt": "The prime minister of India is the head of government of the Republic of India.",
                        "url": "https://example.com/prime-minister-india",
                        "kind": "web",
                        "source": "Web",
                    }
                ]
            ),
        ), patch("app.services.anthropic_client.httpx.AsyncClient", FakeAsyncClient):
            response = self.client.post("/chat", json={"message": "Who is the Prime Minister of India?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "current_affairs")
        self.assertEqual(payload["source_strategy"], "web")
        self.assertEqual(payload["answer"], "The current Prime Minister of India is Narendra Modi.")
        self.assertNotIn("2017", payload["answer"])

    def test_chat_current_office_fallback_uses_structured_web_result(self) -> None:
        settings.ai_provider = "offline"
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Prime Minister of India",
                        "excerpt": "The current Prime Minister of India is Narendra Modi.",
                        "url": "https://www.wikidata.org/wiki/Q1058",
                        "kind": "web",
                        "source": "Wikidata",
                    },
                    {
                        "title": "Prime Minister of India",
                        "excerpt": "The prime minister of India is the head of government of the Republic of India.",
                        "url": "https://example.com/prime-minister-india",
                        "kind": "web",
                        "source": "Web",
                    },
                ]
            ),
        ):
            response = self.client.post("/chat", json={"message": "Who is the Prime Minister of India?"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "current_affairs")
        self.assertEqual(payload["source_strategy"], "web")
        self.assertEqual(payload["memory_confidence"], 0.0)
        self.assertEqual(payload["answer"], "The current Prime Minister of India is Narendra Modi.")
        self.assertNotIn("head of government", payload["answer"].lower())

    def test_chat_public_named_entity_prefers_authoritative_entity_result(self) -> None:
        settings.ai_provider = "offline"
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Narendra Modi Movie Review",
                        "excerpt": "Narendra Modi is a film and movie trailer topic.",
                        "url": "https://example.com/movie",
                        "kind": "web",
                        "source": "DuckDuckGo",
                    },
                    {
                        "title": "Narendra Modi",
                        "excerpt": "Narendra Modi is an Indian politician who has served as prime minister of India since 2014.",
                        "url": "https://en.wikipedia.org/wiki/Narendra_Modi",
                        "kind": "web",
                        "source": "Wikipedia",
                        "authority_score": 0.9,
                        "quality_score": 5.0,
                    },
                ]
            ),
        ):
            response = self.client.post("/chat", json={"message": "who is narendra modi"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "general_knowledge")
        self.assertEqual(payload["source_strategy"], "web")
        self.assertEqual(payload["memory_confidence"], 0.0)
        self.assertIn("Indian politician", payload["answer"])
        self.assertNotIn("movie", payload["answer"].lower())

    def test_chat_president_america_uses_current_office_result(self) -> None:
        settings.ai_provider = "offline"
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "President of United States",
                        "excerpt": "The current President of United States is Example Leader.",
                        "url": "https://www.wikidata.org/wiki/Q11696",
                        "kind": "web",
                        "source": "Wikidata",
                    },
                    {
                        "title": "Phil Baker",
                        "excerpt": "Phil Baker was a radio personality and comedian.",
                        "url": "https://example.com/phil-baker",
                        "kind": "web",
                        "source": "DuckDuckGo",
                    },
                ]
            ),
        ):
            response = self.client.post("/chat", json={"message": "who is president of america"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "current_affairs")
        self.assertEqual(payload["source_strategy"], "web")
        self.assertEqual(payload["answer"], "The current President of United States is Example Leader.")
        self.assertNotIn("phil baker", payload["answer"].lower())

    def test_chat_news_summary_avoids_entertainment_noise(self) -> None:
        settings.ai_provider = "offline"
        settings.online_search_enabled = True

        with patch.object(
            web_lookup_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "title": "Tamil Nadu government announces new measures - The Hindu",
                        "excerpt": "Tamil Nadu government officials announced new public measures today. Source: The Hindu.",
                        "url": "https://www.thehindu.com/news/national/tamil-nadu/example",
                        "kind": "news",
                        "source": "Google News / The Hindu",
                    },
                    {
                        "title": "Jyothika movie trailer trends",
                        "excerpt": "Tamil cinema actress Jyothika stars in a new movie trailer.",
                        "url": "https://example.com/cinema",
                        "kind": "news",
                        "source": "Google News / Entertainment",
                    },
                ]
            ),
        ):
            response = self.client.post("/chat", json={"message": "top news in tamilnadu"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["intent"], "current_affairs")
        self.assertEqual(payload["source_strategy"], "web")
        self.assertIn("Tamil Nadu government announces new measures", payload["answer"])
        self.assertNotIn("jyothika", payload["answer"].lower())

    def test_chat_persists_session_and_restores_saved_messages(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/admin/documents",
            headers=headers,
            json={
                "title": "Haji profile",
                "content": "Haji is the founder behind HajiHaz AI and leads its direction.",
                "tags": ["haji", "profile"],
                "source": "manual",
                "core_persona": True,
            },
        )

        response = self.client.post("/chat", json={"message": "Who is Haji?"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["session_id"])
        self.assertTrue(payload["conversation_title"])

        session_response = self.client.get(f"/chat/session/{payload['session_id']}")
        self.assertEqual(session_response.status_code, 200, session_response.text)
        session_payload = session_response.json()
        self.assertEqual(session_payload["session"]["id"], payload["session_id"])
        self.assertEqual(session_payload["session"]["message_count"], 2)
        self.assertEqual(session_payload["messages"][0]["role"], "user")
        self.assertEqual(session_payload["messages"][1]["role"], "assistant")
        self.assertIn("Haji", session_payload["messages"][1]["content"])

    def test_chat_stream_returns_sse_chunks_and_final_payload(self) -> None:
        with self.client.stream("POST", "/chat/stream", json={"message": "hello macha"}) as response:
            self.assertEqual(response.status_code, 200)
            raw_body = "".join(response.iter_text())

        self.assertIn("event: stage", raw_body)
        self.assertIn("event: session", raw_body)
        self.assertIn("event: delta", raw_body)
        self.assertIn("event: complete", raw_body)

        session_payload = None
        complete_payload = None
        for block in raw_body.split("\n\n"):
            if not block.strip():
                continue
            event_name = ""
            data_payload = ""
            for line in block.splitlines():
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                if line.startswith("data:"):
                    data_payload = line.split(":", 1)[1].strip()
            if event_name == "session":
                session_payload = json.loads(data_payload)
            if event_name == "complete":
                complete_payload = json.loads(data_payload)

        self.assertIsNotNone(session_payload)
        self.assertIsNotNone(complete_payload)
        self.assertEqual(complete_payload["mode"], "conversation")
        self.assertEqual(complete_payload["intent"], "conversation")
        self.assertEqual(complete_payload["source_strategy"], "none")
        self.assertEqual(complete_payload["memory_confidence"], 0.0)
        self.assertTrue(session_payload["session_id"])
        self.assertEqual(complete_payload["session_id"], session_payload["session_id"])
