from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .admin import CustomUserCreationForm
from .models import CustomUser, OTP, UserProfile

PASSWORD = "Str0ngPass!x"
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def make_user(email="user@test.com", verified=True, password=PASSWORD):
    user = CustomUser.objects.create_user(email=email, password=password)
    user.is_verified = verified
    user.save()
    return user


class RegistrationAndOtpTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def register(self):
        response = self.client.post(
            "/api/auth/sign-up/",
            {"email": "new@test.com", "password": PASSWORD, "first_name": "New"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data["user_id"]

    def test_register_sends_otp_without_last_name(self):
        self.register()
        self.assertTrue(OTP.objects.filter(email="new@test.com").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_otp_attempts_are_limited(self):
        user_id = self.register()
        codes = [
            self.client.post("/api/auth/otp/verify/", {"user_id": user_id, "otp": "x"}, format="json").status_code
            for _ in range(6)
        ]
        self.assertEqual(codes, [400] * 5 + [429])

    def test_correct_otp_verifies_and_sets_auth_cookies(self):
        user_id = self.register()
        otp = OTP.objects.get(email="new@test.com").otp
        response = self.client.post("/api/auth/otp/verify/", {"user_id": user_id, "otp": otp}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CustomUser.objects.get(id=user_id).is_verified)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_unknown_user_ids_return_404(self):
        self.assertEqual(self.client.post("/api/auth/otp/create/", {"user_id": 999}, format="json").status_code, 404)
        self.assertEqual(
            self.client.post("/api/auth/otp/verify/", {"user_id": 999, "otp": "1"}, format="json").status_code, 404
        )

    def test_otp_older_than_a_day_is_expired(self):
        otp = OTP(email="z@test.com", otp="123456")
        otp.save()
        OTP.objects.filter(pk=otp.pk).update(created_at=timezone.now() - timedelta(days=1, seconds=30))
        otp.refresh_from_db()
        self.assertTrue(otp.is_expired())


class LoginAndCookieAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, email="user@test.com", password=PASSWORD):
        return self.client.post("/api/auth/sign-in/", {"email": email, "password": password}, format="json")

    def test_unverified_login_gets_new_otp_and_no_tokens(self):
        user = make_user(verified=False)
        response = self.login()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["user_id"], user.id)
        self.assertNotIn("access_token", response.data)
        self.assertTrue(OTP.objects.filter(email=user.email).exists())

    def test_login_creates_missing_profile_and_sets_cookies(self):
        user = make_user()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertIn("access_token", response.cookies)

    def test_wrong_password_returns_401(self):
        make_user()
        self.assertEqual(self.login(password="nope").status_code, 401)

    def test_cookie_authenticates_requests(self):
        make_user()
        self.login()
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_password"])

    def test_unsafe_cookie_request_requires_csrf_header(self):
        make_user()
        self.login()
        body = {"current_password": PASSWORD, "new_password": "An0ther!Pass"}
        self.assertEqual(self.client.post("/api/auth/password-change/", body, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/auth/password-change/", body, format="json", **AJAX).status_code, 200)

    def test_invalid_cookie_does_not_block_sign_in(self):
        make_user()
        self.client.cookies["access_token"] = "garbage"
        self.assertEqual(self.login().status_code, 200)

    def test_refresh_from_cookie_and_logout(self):
        make_user()
        self.login()
        response = self.client.post("/api/auth/refresh/", **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)

        response = self.client.post("/api/auth/logout/", **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)

    def test_refresh_without_token_returns_401(self):
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)


@override_settings(GOOGLE_CLIENT_IDS=["client-id"])
class GoogleLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def fake_google(self, aud="client-id", email="g@test.com"):
        def fake_get(url, **kwargs):
            if "tokeninfo" in url:
                return mock.Mock(status_code=200, json=lambda: {"aud": aud})
            return mock.Mock(status_code=200, json=lambda: {
                "email": email, "email_verified": True, "name": "G User", "picture": "http://p",
            })
        return mock.patch("authentications.views.http_requests.get", side_effect=fake_get)

    def test_token_is_required(self):
        response = self.client.post("/api/auth/google-login/", {"email": "a@test.com"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_valid_access_token_uses_googles_email(self):
        with self.fake_google():
            response = self.client.post(
                "/api/auth/google-login/", {"access_token": "ok", "email": "attacker@test.com"}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email_address"], "g@test.com")
        self.assertFalse(CustomUser.objects.get(email="g@test.com").has_usable_password())

    def test_token_for_another_app_is_rejected(self):
        with self.fake_google(aud="someone-else"):
            response = self.client.post("/api/auth/google-login/", {"access_token": "ok"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_google_user_has_no_password_to_change(self):
        with self.fake_google():
            self.client.post("/api/auth/google-login/", {"access_token": "ok"}, format="json")
        self.assertFalse(self.client.get("/api/auth/profile/").data["has_password"])
        response = self.client.post(
            "/api/auth/password-change/", {"current_password": "x", "new_password": "An0ther!Pass"},
            format="json", **AJAX,
        )
        self.assertEqual(response.status_code, 400)


class AdminFormTests(TestCase):
    def test_admin_creation_form_hashes_password(self):
        form = CustomUserCreationForm(data={
            "email": "adm@test.com", "role": "user", "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().check_password(PASSWORD))
