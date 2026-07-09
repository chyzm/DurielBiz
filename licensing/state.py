import hashlib
import hmac
import json
import os
from pathlib import Path

STATE_FILENAME = ".license_state.json"
DEFAULT_REGISTRY_KEY_PATH = "SOFTWARE\\DurielTech\\DurielBizPOS"

# Local-only obfuscation key so a casual text-editor tamper of the state file/registry
# value is detected. This is NOT the security boundary for the license itself — that's
# the Ed25519 signature in keys.py, which this secret cannot forge.
_INTEGRITY_SECRET = b"durielbiz-license-state-integrity-v1"


def _registry_key_path() -> str:
    return os.environ.get("DURIELBIZ_LICENSE_REGISTRY_KEY", DEFAULT_REGISTRY_KEY_PATH)


def _state_file_path() -> Path:
    data_root = os.environ.get("DURIELBIZ_DATA_DIR")
    base_path = Path(data_root) if data_root else Path.cwd()
    return base_path / STATE_FILENAME


def _sign_state(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True).encode("utf-8")
    return hmac.new(_INTEGRITY_SECRET, blob, hashlib.sha256).hexdigest()


def _read_file_state():
    path = _state_file_path()
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        data = envelope.get("data")
        signature = envelope.get("signature", "")
    except (json.JSONDecodeError, OSError, TypeError, AttributeError):
        return None
    if not data or not hmac.compare_digest(_sign_state(data), signature):
        return None
    return data


def _write_file_state(data: dict) -> None:
    path = _state_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"data": data, "signature": _sign_state(data)}
    path.write_text(json.dumps(envelope), encoding="utf-8")


def _read_registry_state():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _registry_key_path()) as key:
            raw, _ = winreg.QueryValueEx(key, "State")
        envelope = json.loads(raw)
        data = envelope.get("data")
        signature = envelope.get("signature", "")
    except Exception:
        return None
    if not data or not hmac.compare_digest(_sign_state(data), signature):
        return None
    return data


def _write_registry_state(data: dict) -> None:
    try:
        import winreg

        envelope = json.dumps({"data": data, "signature": _sign_state(data)})
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _registry_key_path())
        winreg.SetValueEx(key, "State", 0, winreg.REG_SZ, envelope)
        winreg.CloseKey(key)
    except Exception:
        pass


def load_state():
    """Return the more trustworthy of the two redundant stores: whichever has the
    EARLIEST recorded trial_started_at survives, so deleting or editing just one
    store can't reset or extend the trial on its own."""
    candidates = [state for state in (_read_file_state(), _read_registry_state()) if state]
    if not candidates:
        return None
    return min(candidates, key=lambda state: state.get("trial_started_at") or "")


def save_state(data: dict) -> None:
    _write_file_state(data)
    _write_registry_state(data)


def clear_state() -> None:
    """Test/dev helper: remove both stores."""
    try:
        _state_file_path().unlink()
    except OSError:
        pass
    try:
        import winreg

        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _registry_key_path())
    except Exception:
        pass
