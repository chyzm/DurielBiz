import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import state as state_store
from .fingerprint import get_hardware_fingerprint
from .services import activate_license, get_license_status

MASTER_KEY = "test-master-activation-key-do-not-use-in-prod"
MASTER_KEY_HASH = hashlib.sha256(MASTER_KEY.encode("utf-8")).hexdigest()


class LicensingTestBase(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.env_patcher = mock.patch.dict(
            os.environ,
            {
                "DURIELBIZ_DATA_DIR": self.tmp_dir,
                "DURIELBIZ_LICENSE_REGISTRY_KEY": "SOFTWARE\\DurielTechTests\\LicensingTests",
            },
        )
        self.env_patcher.start()
        state_store.clear_state()

    def tearDown(self):
        state_store.clear_state()
        self.env_patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class FingerprintTests(TestCase):
    def test_fingerprint_is_stable_and_well_formed(self):
        first = get_hardware_fingerprint()
        second = get_hardware_fingerprint()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)


class StateStorageTests(LicensingTestBase):
    def test_save_and_load_round_trip(self):
        state_store.save_state({"trial_started_at": "2026-01-01T00:00:00+00:00"})
        loaded = state_store.load_state()
        self.assertEqual(loaded["trial_started_at"], "2026-01-01T00:00:00+00:00")

    def test_deleting_file_store_does_not_lose_earliest_date(self):
        state_store.save_state({"trial_started_at": "2026-01-01T00:00:00+00:00"})
        (state_store._state_file_path()).unlink()  # simulate wiping app data dir
        loaded = state_store.load_state()
        self.assertEqual(loaded["trial_started_at"], "2026-01-01T00:00:00+00:00")

    def test_tampered_file_is_ignored(self):
        state_store.save_state({"trial_started_at": "2026-01-01T00:00:00+00:00"})
        path = state_store._state_file_path()
        path.write_text('{"data": {"trial_started_at": "2020-01-01T00:00:00+00:00"}, "signature": "forged"}')
        loaded = state_store.load_state()
        # File store fails HMAC check, so only the (still-intact) registry copy is trusted.
        self.assertEqual(loaded["trial_started_at"], "2026-01-01T00:00:00+00:00")


class LicenseStatusTests(LicensingTestBase):
    def test_first_run_starts_trial(self):
        status = get_license_status()
        self.assertFalse(status["licensed"])
        self.assertTrue(status["trial_active"])
        self.assertEqual(status["days_left"], 14)

    def test_trial_counts_down(self):
        started = (datetime.now(dt_timezone.utc) - timedelta(days=5)).isoformat()
        state_store.save_state({"trial_started_at": started})
        status = get_license_status()
        self.assertTrue(status["trial_active"])
        self.assertEqual(status["days_left"], 9)

    def test_trial_expires_after_14_days(self):
        started = (datetime.now(dt_timezone.utc) - timedelta(days=20)).isoformat()
        state_store.save_state({"trial_started_at": started})
        status = get_license_status()
        self.assertFalse(status["licensed"])
        self.assertFalse(status["trial_active"])
        self.assertEqual(status["days_left"], 0)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activation_with_correct_key_locks_to_this_machine(self):
        activate_license(MASTER_KEY)
        status = get_license_status()
        self.assertTrue(status["licensed"])

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activation_rejects_wrong_key(self):
        with self.assertRaises(ValueError):
            activate_license("totally-wrong-key")
        self.assertFalse(get_license_status()["licensed"])

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activation_rejects_empty_key(self):
        with self.assertRaises(ValueError):
            activate_license("")

    def test_activation_fails_when_licensing_not_configured(self):
        with self.assertRaises(ValueError):
            activate_license(MASTER_KEY)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activated_state_copied_to_another_machine_is_not_licensed(self):
        activate_license(MASTER_KEY)
        state = state_store.load_state()
        self.assertEqual(state["activated_fingerprint"], get_hardware_fingerprint())

        # Simulate copying the state file to a machine with a different fingerprint.
        with mock.patch("licensing.services.get_hardware_fingerprint", return_value="A-DIFFERENT-MACHINES-FINGERPRINT"):
            status = get_license_status()
        self.assertFalse(status["licensed"])


class LicenseGateMiddlewareTests(LicensingTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_inert_when_not_desktop_mode(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)

    @override_settings(LICENSE_MASTER_KEY_HASH="")
    def test_inert_when_no_master_key_configured(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_blocks_when_desktop_and_trial_expired(self):
        started = (datetime.now(dt_timezone.utc) - timedelta(days=20)).isoformat()
        state_store.save_state({"trial_started_at": started})
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/accounts/login/")
        self.assertRedirects(response, reverse("licensing:activate"), fetch_redirect_response=False)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_allows_activation_page_even_when_expired(self):
        started = (datetime.now(dt_timezone.utc) - timedelta(days=20)).isoformat()
        state_store.save_state({"trial_started_at": started})
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/licensing/activate/")
        self.assertEqual(response.status_code, 200)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_allows_through_during_active_trial(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activation_view_accepts_correct_key_end_to_end(self):
        started = (datetime.now(dt_timezone.utc) - timedelta(days=20)).isoformat()
        state_store.save_state({"trial_started_at": started})
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.post("/licensing/activate/", {"activation_key": MASTER_KEY})
            self.assertRedirects(response, reverse("accounts:login"), fetch_redirect_response=False)
            follow_up = self.client.get("/accounts/login/")
        self.assertEqual(follow_up.status_code, 200)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activation_view_rejects_wrong_key_end_to_end(self):
        started = (datetime.now(dt_timezone.utc) - timedelta(days=20)).isoformat()
        state_store.save_state({"trial_started_at": started})
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.post("/licensing/activate/", {"activation_key": "wrong-key"})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "not valid")
            still_blocked = self.client.get("/accounts/login/")
        self.assertRedirects(still_blocked, reverse("licensing:activate"), fetch_redirect_response=False)

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_activate_page_shows_locked_state_once_already_licensed(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            self.client.post("/licensing/activate/", {"activation_key": MASTER_KEY})
            response = self.client.get("/licensing/activate/")
        self.assertContains(response, "already activated")
        self.assertContains(response, "disabled")

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_reactivation_post_is_a_no_op_once_licensed(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            self.client.post("/licensing/activate/", {"activation_key": MASTER_KEY})
            # A second POST (even with a wrong key) should not error or change anything.
            response = self.client.post("/licensing/activate/", {"activation_key": "garbage"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already activated")


class AboutSupportLicensePanelTests(LicensingTestBase):
    def setUp(self):
        super().setUp()
        from accounts.models import User

        self.user = User.objects.create_user(username="panel_admin", password="pass1234", role=User.Role.ADMIN, is_staff=True)
        self.client.login(username="panel_admin", password="pass1234")

    def test_panel_hidden_when_not_desktop_mode(self):
        response = self.client.get("/accounts/about-support/")
        self.assertNotContains(response, "Licensing</h2>")

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_panel_shows_trial_countdown(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            response = self.client.get("/accounts/about-support/")
        self.assertContains(response, "Trial mode")
        self.assertContains(response, "Activate</a>")

    @override_settings(LICENSE_MASTER_KEY_HASH=MASTER_KEY_HASH)
    def test_panel_shows_licensed_with_disabled_button(self):
        with mock.patch.dict(os.environ, {"DURIELBIZ_DESKTOP": "1"}):
            self.client.post("/licensing/activate/", {"activation_key": MASTER_KEY})
            response = self.client.get("/accounts/about-support/")
        self.assertContains(response, "Licensed</span>")
        self.assertContains(response, "disabled")
