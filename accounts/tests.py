import os
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import ActivityLog, User


class AdminAssistedPasswordResetTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_test", password="AdminPass123!", role=User.Role.ADMIN, is_staff=True
        )
        self.target = User.objects.create_user(
            username="target_test", password="OldPass123!", role=User.Role.CASHIER
        )

    def test_admin_can_reset_another_users_password_and_force_change(self):
        self.client.login(username="admin_test", password="AdminPass123!")

        response = self.client.post(
            f"/accounts/users/{self.target.pk}/reset-password/",
            {
                "new_password1": "NewPass123!",
                "new_password2": "NewPass123!",
                "force_change_at_next_login": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("NewPass123!"))
        self.assertTrue(self.target.must_change_password)

    def test_forced_password_change_flow(self):
        self.target.set_password("NewPass123!")
        self.target.must_change_password = True
        self.target.save()

        self.client.login(username="target_test", password="NewPass123!")
        response = self.client.get("/accounts/home/", follow=True)
        self.assertIn(
            ("/accounts/password-change/required/", 302),
            response.redirect_chain,
        )

        response = self.client.post(
            "/accounts/password-change/required/",
            {"new_password1": "FinalPass123!", "new_password2": "FinalPass123!"},
        )
        self.assertEqual(response.status_code, 302)

        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)
        self.assertTrue(self.target.check_password("FinalPass123!"))

    def test_admin_cannot_reset_own_password_via_admin_route(self):
        self.client.login(username="admin_test", password="AdminPass123!")
        response = self.client.post(
            f"/accounts/users/{self.admin.pk}/reset-password/",
            {"new_password1": "X", "new_password2": "X"},
            follow=True,
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("AdminPass123!"))

    def test_non_admin_cannot_reset_passwords(self):
        self.client.login(username="target_test", password="OldPass123!")
        response = self.client.get(f"/accounts/users/{self.admin.pk}/reset-password/")
        self.assertEqual(response.status_code, 302)


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="throttle_user", password="CorrectPass123!", role=User.Role.ADMIN)

    def test_repeated_failed_logins_are_throttled(self):
        for _ in range(8):
            response = self.client.post("/accounts/login/", {"username": "throttle_user", "password": "wrong"})
            self.assertEqual(response.status_code, 200)

        response = self.client.post("/accounts/login/", {"username": "throttle_user", "password": "CorrectPass123!"})
        self.assertContains(response, "Too many failed login attempts")

    def test_successful_logins_do_not_count_toward_throttle(self):
        for _ in range(10):
            self.client.login(username="throttle_user", password="CorrectPass123!")
            self.client.logout()

        response = self.client.post("/accounts/login/", {"username": "throttle_user", "password": "CorrectPass123!"})
        self.assertEqual(response.status_code, 302)

    def test_failed_login_is_logged_with_ip(self):
        self.client.post("/accounts/login/", {"username": "throttle_user", "password": "wrong"})
        log = ActivityLog.objects.filter(action="login_failed").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ip_address, "127.0.0.1")


class PageRenderSmokeTests(TestCase):
    """Renders every sidebar-linked page to catch template errors after the base.html refactor."""

    def setUp(self):
        self.admin = User.objects.create_user(username="smoke_admin", password="pass1234", role=User.Role.ADMIN, is_staff=True)

    def test_admin_pages_render(self):
        self.client.login(username="smoke_admin", password="pass1234")
        urls = [
            "/dashboard/",
            "/sales/pos/",
            "/products/",
            "/products/categories/",
            "/suppliers/",
            "/purchases/",
            "/inventory/",
            "/sales/customers/",
            "/sales/history/",
            "/reports/category/",
            "/reports/profit/",
            "/accounts/activity-log/",
            "/branches/",
            "/settings/business/",
            "/accounts/admin-center/",
            "/accounts/password-change/local/",
            "/accounts/about-support/",
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"{url} returned {response.status_code}")

    def test_login_page_renders_logged_out(self):
        self.client.logout()
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)


class LoginCloudDetectionTests(TestCase):
    """Verifies the Username/Email label switch and the local dev preview toggle."""

    def test_local_host_shows_username(self):
        response = self.client.get("/accounts/login/", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Username<")
        self.assertNotContains(response, ">Email<")

    def test_cloud_host_shows_email(self):
        response = self.client.get("/accounts/login/", HTTP_HOST="durieltech.pythonanywhere.com")
        self.assertContains(response, ">Email<")
        self.assertNotContains(response, ">Username<")

    def test_localhost_cloud_next_shows_email(self):
        response = self.client.get("/accounts/login/?next=/cloud/purchases/", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Email<")
        self.assertNotContains(response, ">Username<")

    @override_settings(DEBUG=True)
    def test_preview_toggle_switches_label_with_debug_on(self):
        response = self.client.get("/accounts/login/?mode=cloud", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Email<")
        response = self.client.get("/accounts/login/?mode=local", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Username<")

    @override_settings(DEBUG=False)
    def test_preview_toggle_switches_label_with_debug_off(self):
        # Regression test: this used to be silently inert whenever DEBUG was False
        # (e.g. a local .env with "Debug=false"), even on plain localhost dev runs.
        response = self.client.get("/accounts/login/?mode=cloud", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Email<")
        response = self.client.get("/accounts/login/?mode=local", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Username<")

    def test_preview_toggle_is_inert_for_real_desktop_app(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/accounts/login/?mode=cloud", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Username<")
        self.assertNotContains(response, ">Email<")

    def test_cloud_next_is_inert_for_real_desktop_app(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/accounts/login/?next=/cloud/purchases/", HTTP_HOST="127.0.0.1:9000")
        self.assertContains(response, ">Username<")
        self.assertNotContains(response, ">Email<")


class CookieSecurityRegressionTests(TestCase):
    """Regression guard: session/CSRF cookies must never be Secure-only unless we're
    actually behind a trusted HTTPS origin — otherwise browsers silently refuse to store
    or send them over plain http://, which looks exactly like being logged out on every
    request. This must hold regardless of DEBUG, since local/.env DEBUG=False is common."""

    def test_cookies_are_not_secure_without_an_https_trusted_origin(self):
        from django.conf import settings

        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])
        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        self.assertFalse(settings.CSRF_COOKIE_SECURE)

    def test_csrf_cookie_has_no_secure_attribute_over_plain_http(self):
        response = self.client.get("/accounts/login/", HTTP_HOST="127.0.0.1:9000")
        csrf_cookie = response.cookies.get("csrftoken")
        self.assertIsNotNone(csrf_cookie)
        self.assertEqual(csrf_cookie["secure"], "")
