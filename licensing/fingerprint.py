import hashlib
import platform


def _read_windows_machine_guid() -> str:
    import winreg

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return value


def get_hardware_fingerprint() -> str:
    """A stable identifier for this Windows installation, used to lock license
    keys to a single machine. Falls back to the hostname off-Windows (dev only)."""
    try:
        raw = _read_windows_machine_guid()
    except Exception:
        raw = platform.node()
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:32].upper()
