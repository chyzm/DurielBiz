from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from unittest import mock

from accounts.models import EmailOTP, User


class CloudPasswordResetOTPTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="cloud_user", email="cloud_user@example.com", password="OldPass123!", role=User.Role.ADMIN
        )
        self.cloud_host = "durieltech.pythonanywhere.com"

    def test_request_sends_otp_email_for_existing_user(self):
        response = self.client.post(
            "/accounts/password-reset/", {"email": "cloud_user@example.com"}, HTTP_HOST=self.cloud_host
        )
        self.assertRedirects(response, "/accounts/password-reset/done/", fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verification code", mail.outbox[0].body.lower())
        otp = EmailOTP.objects.get(email="cloud_user@example.com", purpose=EmailOTP.Purpose.PASSWORD_RESET)
        self.assertTrue(otp.is_valid())

    def test_request_does_not_leak_whether_email_exists(self):
        response = self.client.post(
            "/accounts/password-reset/", {"email": "nobody@example.com"}, HTTP_HOST=self.cloud_host
        )
        self.assertRedirects(response, "/accounts/password-reset/done/", fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_delivery_failure_does_not_crash_reset_request(self):
        with mock.patch("accounts.views.send_otp_email", side_effect=OSError("Network is unreachable")):
            with self.assertLogs("accounts.views", level="ERROR"):
                response = self.client.post(
                    "/accounts/password-reset/",
                    {"email": "cloud_user@example.com"},
                    HTTP_HOST=self.cloud_host,
                )

        self.assertRedirects(response, "/accounts/password-reset/done/", fetch_redirect_response=False)
        otp = EmailOTP.objects.get(email="cloud_user@example.com", purpose=EmailOTP.Purpose.PASSWORD_RESET)
        self.assertTrue(otp.is_used)

    def test_verify_with_correct_code_resets_password(self):
        self.client.post("/accounts/password-reset/", {"email": "cloud_user@example.com"}, HTTP_HOST=self.cloud_host)
        otp = EmailOTP.objects.get(email="cloud_user@example.com", purpose=EmailOTP.Purpose.PASSWORD_RESET)

        response = self.client.post(
            "/accounts/reset/verify/",
            {"code": otp.code, "new_password1": "BrandNewPass123!", "new_password2": "BrandNewPass123!"},
            HTTP_HOST=self.cloud_host,
        )
        self.assertRedirects(response, "/accounts/reset/done/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass123!"))
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_verify_with_wrong_code_does_not_reset_password(self):
        self.client.post("/accounts/password-reset/", {"email": "cloud_user@example.com"}, HTTP_HOST=self.cloud_host)
        response = self.client.post(
            "/accounts/reset/verify/",
            {"code": "000000", "new_password1": "BrandNewPass123!", "new_password2": "BrandNewPass123!"},
            HTTP_HOST=self.cloud_host,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid or has expired")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass123!"))

    def test_mismatched_password_confirmation_does_not_consume_otp(self):
        self.client.post("/accounts/password-reset/", {"email": "cloud_user@example.com"}, HTTP_HOST=self.cloud_host)
        otp = EmailOTP.objects.get(email="cloud_user@example.com", purpose=EmailOTP.Purpose.PASSWORD_RESET)

        response = self.client.post(
            "/accounts/reset/verify/",
            {"code": otp.code, "new_password1": "BrandNewPass123!", "new_password2": "Mismatch123!"},
            HTTP_HOST=self.cloud_host,
        )
        self.assertEqual(response.status_code, 200)
        otp.refresh_from_db()
        self.assertFalse(otp.is_used)

        # The still-valid code should work on a second, correctly-confirmed attempt.
        response = self.client.post(
            "/accounts/reset/verify/",
            {"code": otp.code, "new_password1": "BrandNewPass123!", "new_password2": "BrandNewPass123!"},
            HTTP_HOST=self.cloud_host,
        )
        self.assertRedirects(response, "/accounts/reset/done/", fetch_redirect_response=False)

    def test_local_desktop_host_cannot_access_otp_reset(self):
        response = self.client.get("/accounts/password-reset/", HTTP_HOST="127.0.0.1:9000")
        self.assertRedirects(response, "/accounts/login/")
