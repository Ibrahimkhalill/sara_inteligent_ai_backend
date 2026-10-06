from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentications.models import CustomUser
from . import jobs
from .models import FCMToken, Notification


class FcmTokenTests(TestCase):
    def test_token_moves_to_the_user_now_logged_in(self):
        first = CustomUser.objects.create_user(email="a@test.com", password="x")
        second = CustomUser.objects.create_user(email="b@test.com", password="x")
        for user in (first, second):
            client = APIClient()
            client.force_authenticate(user)
            response = client.post("/api/notification/save-fcm-token/", {"fcm_token": "tok"}, format="json")
            self.assertEqual(response.status_code, 200)
        token = FCMToken.objects.get(token="tok")
        self.assertEqual(token.user, second)
        self.assertIn("b@test.com", str(token))


class SendDueNotificationsTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email="n@test.com", password="x")
        FCMToken.objects.create(user=self.user, token="tok")
        for _ in range(3):
            Notification.objects.create(user=self.user, message="m", notify_at=timezone.now() - timedelta(minutes=1))

    def test_each_notification_is_sent_once(self):
        with mock.patch("notification.jobs.send_fcm_notification", return_value={"success": True}) as send:
            jobs.send_due_notifications()
            jobs.send_due_notifications()
        self.assertEqual(send.call_count, 3)
        self.assertFalse(Notification.objects.filter(sent=False).exists())

    def test_unregistered_tokens_are_deleted(self):
        result = {"success": False, "unregistered": True}
        with mock.patch("notification.jobs.send_fcm_notification", return_value=result):
            jobs.send_due_notifications()
        self.assertFalse(FCMToken.objects.filter(token="tok").exists())
