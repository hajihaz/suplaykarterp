from __future__ import annotations

from test_support import AppTestCase


class EndToEndSmokeTests(AppTestCase):
    def test_admin_to_chat_flow_with_grounded_retrieval(self) -> None:
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        import_response = self.client.post(
            "/admin/documents/import",
            headers=headers,
            json={
                "skip_duplicates": True,
                "documents": [
                    {
                        "title": "Warranty policy",
                        "content": "All warranty claims must be acknowledged within 48 hours and escalated to support operations.",
                        "tags": ["support", "policy"],
                        "source": "upload",
                    },
                    {
                        "title": "Client onboarding",
                        "content": "Every new client onboarding should include kickoff notes, owner assignment, and next-step timelines.",
                        "tags": ["client", "ops"],
                        "source": "upload",
                    },
                ],
            },
        )
        self.assertEqual(import_response.status_code, 200, import_response.text)
        imported_ids = [document["id"] for document in import_response.json()["documents"]]

        chat_response = self.client.post(
            "/chat",
            json={"message": "What is the warranty claim response window?"},
        )
        self.assertEqual(chat_response.status_code, 200, chat_response.text)
        payload = chat_response.json()
        self.assertTrue(payload["answer"])
        self.assertTrue(payload["citations"])
        self.assertIn("Warranty policy", [citation["title"] for citation in payload["citations"]])

        list_response = self.client.get("/admin/documents", headers=headers)
        self.assertEqual(list_response.status_code, 200, list_response.text)
        listed_ids = {document["id"] for document in list_response.json()}
        for document_id in imported_ids:
            self.assertIn(document_id, listed_ids)

        for document_id in imported_ids:
            delete_response = self.client.delete(f"/admin/documents/{document_id}", headers=headers)
            self.assertEqual(delete_response.status_code, 200, delete_response.text)

        logout_response = self.client.post("/auth/logout", headers=headers)
        self.assertEqual(logout_response.status_code, 200, logout_response.text)
