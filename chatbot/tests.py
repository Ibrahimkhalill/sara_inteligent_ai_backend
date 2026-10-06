from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentications.models import CustomUser
from . import views


class ChatbotTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(CustomUser.objects.create_user(email="c@test.com", password="x"))

    def test_requires_login(self):
        response = APIClient().post("/api/chatbot/ai-chat/", {"message": "hi"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_rejects_invalid_history(self):
        for messages in ([{"role": "system", "content": "x"}], [{"role": "assistant", "content": "x"}], []):
            response = self.client.post("/api/chatbot/ai-chat/", {"messages": messages}, format="json")
            self.assertEqual(response.status_code, 400, messages)

    def test_sends_roles_and_context_to_gemini(self):
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["body"] = json
            return mock.Mock(
                raise_for_status=lambda: None,
                json=lambda: {"candidates": [{"content": {"parts": [{"text": "Hi there"}]}}]},
            )

        with mock.patch.object(views, "GEMINI_API_KEY", "key"), \
                mock.patch("chatbot.views.requests.post", side_effect=fake_post):
            response = self.client.post("/api/chatbot/ai-chat/", {
                "context": "EMAIL BODY",
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "yo"},
                    {"role": "user", "content": "summarize"},
                ],
            }, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Hi there")
        self.assertEqual([c["role"] for c in captured["body"]["contents"]], ["user", "model", "user"])
        self.assertIn("EMAIL BODY", captured["body"]["system_instruction"]["parts"][0]["text"])

    def test_reports_missing_configuration(self):
        with mock.patch.object(views, "GEMINI_API_KEY", None), mock.patch.object(views, "OPENAI_API_KEY", None):
            response = self.client.post("/api/chatbot/ai-chat/", {"message": "hi"}, format="json")
        self.assertEqual(response.status_code, 500)
