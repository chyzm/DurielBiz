import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from a deterministic location.
load_dotenv(BASE_DIR / ".env")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def decrypt_env_value(value: str) -> str:
    if not value or not (value.startswith("ENC(") and value.endswith(")")):
        return value
    encryption_key = os.getenv("DURIELBIZ_ENV_KEY")
    if not encryption_key:
        raise ImproperlyConfigured("DURIELBIZ_ENV_KEY is required to decrypt ENC(...) environment values.")
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise ImproperlyConfigured("Install 'cryptography' to use encrypted environment values.") from exc
    encrypted_value = value[4:-1]
    try:
        return Fernet(encryption_key.encode("utf-8")).decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise ImproperlyConfigured("Failed to decrypt an ENC(...) environment value.") from exc


def env(name: str, default=None):
    value = os.getenv(name)
    if value is None:
        return default
    return decrypt_env_value(value)


def env_str(name: str, default: str = "") -> str:
    value = env(name, default)
    return str(value if value is not None else default)


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = env(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def env_list(name: str, default=None):
    value = env(name)
    if value is None:
        return default or []
    return [item.strip() for item in str(value).split(",") if item.strip()]


load_env_file(BASE_DIR / ".env")

SECRET_KEY = env_str("SECRET_KEY", "django-insecure-change-me")
debug_env = env("DEBUG")
if debug_env is None:
    DEBUG = os.getenv("DURIELBIZ_DESKTOP") != "1"
else:
    DEBUG = debug_env.lower() in {"1", "true", "yes", "on"}
    
ALLOWED_HOSTS = ["127.0.0.1", 
                 "localhost", 
                 "DurielTech.pythonanywhere.com", 
                 "https://durieltech.com.ng", 
                 "http://www.durieltech.com.ng", 
                 "www.durieltech.com.ng"]

extra_allowed_hosts = env_list("DURIELBIZ_ALLOWED_HOSTS")
if extra_allowed_hosts:
    ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, *extra_allowed_hosts]))
CSRF_TRUSTED_ORIGINS = env_list("DURIELBIZ_CSRF_TRUSTED_ORIGINS")

IS_DESKTOP = os.getenv("DURIELBIZ_DESKTOP") == "1"
# Deliberately NOT keyed off DEBUG: DEBUG is routinely False for local dev/testing too
# (see .env.example, and this project's own desktop default), which would otherwise mark
# session/CSRF cookies Secure-only on a plain http://127.0.0.1 connection — browsers then
# silently refuse to store/send them, which looks exactly like being logged out on every
# request. Only the real HTTPS-fronted cloud deployment sets a trusted https:// origin.
SERVED_OVER_HTTPS = any(origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS)

# The desktop app is served over plain http://127.0.0.1, so cookie/HSTS hardening
# that assumes HTTPS is only applied to the cloud deployment.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = SERVED_OVER_HTTPS and not IS_DESKTOP
CSRF_COOKIE_SECURE = SERVED_OVER_HTTPS and not IS_DESKTOP
SECURE_HSTS_SECONDS = 31536000 if (SERVED_OVER_HTTPS and not IS_DESKTOP) else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
X_FRAME_OPTIONS = "DENY"

if not DEBUG and SECRET_KEY == "django-insecure-change-me":
    import warnings

    warnings.warn(
        "DURIELBIZ: SECRET_KEY is using the insecure default. Set SECRET_KEY in your .env file before deploying.",
        RuntimeWarning,
        stacklevel=1,
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "products",
    "suppliers",
    "inventory",
    "purchases",
    "sales",
    "reports",
    "notifications",
    "cloudsync",
    "invoicing",
    "licensing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "licensing.middleware.LicenseGateMiddleware",
    "invoicing.middleware.InvoicingIdleTimeoutMiddleware",
]

# Desktop-only trial/licensing (see licensing/). Inert unless DURIELBIZ_DESKTOP=1 and
# a master key hash is configured, so cloud deployments and local dev are never gated.
LICENSE_MASTER_KEY_HASH = env("LICENSE_MASTER_KEY_HASH", "")
LICENSE_TRIAL_DAYS = env_int("LICENSE_TRIAL_DAYS", 14)

ROOT_URLCONF = "pos_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "reports.context_processors.business_settings",
            ],
        },
    }
]

WSGI_APPLICATION = "pos_system.wsgi.application"
ASGI_APPLICATION = "pos_system.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(env_str("DURIELBIZ_DATA_DIR", str(BASE_DIR))) / "db.sqlite3",
    }
}

if "test" in sys.argv:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "durielbiz-test-cache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "throttle_cache",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Serve static files straight from STATICFILES_DIRS via WhiteNoise, without requiring
# collectstatic to have run first. The desktop build never runs collectstatic, so this
# keeps static files working there; it also makes the cloud deployment work correctly
# through the real WSGI process (unlike runserver, WSGI servers never auto-serve static
# files on their own).
WHITENOISE_USE_FINDERS = True

EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@durieltech.com.ng")
ADMIN_NOTIFICATION_EMAIL = env_str("ADMIN_NOTIFICATION_EMAIL", DEFAULT_FROM_EMAIL)
DURIELBIZ_SITE_URL = env_str("DURIELBIZ_SITE_URL", "https://DurielTech.pythonanywhere.com")
INVOICING_TRIAL_HOURS = env_int("INVOICING_TRIAL_HOURS", 48)
INVOICING_ALLOW_LOCAL = env_bool("INVOICING_ALLOW_LOCAL", DEBUG and os.getenv("DURIELBIZ_DESKTOP") != "1")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "accounts:login"
LOGIN_URL = "accounts:login"
CSRF_FAILURE_VIEW = "pos_system.error_views.csrf_failure"
