import hashlib
import hmac
from datetime import datetime, timezone as dt_timezone

from django.conf import settings

from . import state as state_store
from .fingerprint import get_hardware_fingerprint


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def get_license_status() -> dict:
    fingerprint = get_hardware_fingerprint()
    current_state = state_store.load_state() or {}

    if current_state.get("activated_fingerprint") == fingerprint:
        return {"licensed": True, "trial_active": False, "days_left": None, "fingerprint": fingerprint}

    trial_started_at = current_state.get("trial_started_at")
    if not trial_started_at:
        trial_started_at = datetime.now(dt_timezone.utc).isoformat()
        state_store.save_state({**current_state, "trial_started_at": trial_started_at, "fingerprint": fingerprint})

    elapsed_days = (datetime.now(dt_timezone.utc) - _parse_iso(trial_started_at)).days
    days_left = max(settings.LICENSE_TRIAL_DAYS - elapsed_days, 0)

    return {
        "licensed": False,
        "trial_active": days_left > 0,
        "days_left": days_left,
        "fingerprint": fingerprint,
    }


def activate_license(entered_key: str) -> None:
    """Verify the entered key against the stored hash and, on success, lock
    activation to THIS machine's current hardware fingerprint. An activated
    state copied to another machine will not match that machine's fingerprint
    and will not be treated as licensed there."""
    entered_key = (entered_key or "").strip()
    if not entered_key:
        raise ValueError("Enter the activation key.")
    if not settings.LICENSE_MASTER_KEY_HASH:
        raise ValueError("Licensing is not configured on this build.")

    entered_hash = hashlib.sha256(entered_key.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(entered_hash, settings.LICENSE_MASTER_KEY_HASH):
        raise ValueError("That activation key is not valid.")

    fingerprint = get_hardware_fingerprint()
    current_state = state_store.load_state() or {}
    state_store.save_state(
        {
            **current_state,
            "activated_fingerprint": fingerprint,
            "activated_at": datetime.now(dt_timezone.utc).isoformat(),
        }
    )
