import os
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

SECRET_KEY = env("SECRET_KEY", "django-insecure-change-me")
debug_env = env("DEBUG")
if debug_env is None:
    DEBUG = os.getenv("DURIELBIZ_DESKTOP") != "1"
else:
    DEBUG = debug_env.lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "DurielTech.pythonanywhere.com"]
extra_allowed_hosts = [
    host.strip()
    for host in env("DURIELBIZ_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if extra_allowed_hosts:
    ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, *extra_allowed_hosts]))
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in env("DURIELBIZ_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "invoicing.middleware.InvoicingIdleTimeoutMiddleware",
]

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
        "NAME": Path(env("DURIELBIZ_DATA_DIR", str(BASE_DIR))) / "db.sqlite3",
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

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = str(env("EMAIL_USE_TLS", "True")).lower() in ("true", "1", "yes")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@durieltech.com.ng")
ADMIN_NOTIFICATION_EMAIL = env("ADMIN_NOTIFICATION_EMAIL", DEFAULT_FROM_EMAIL)
DURIELBIZ_SITE_URL = env("DURIELBIZ_SITE_URL", "https://DurielTech.pythonanywhere.com")
INVOICING_TRIAL_HOURS = env_int("INVOICING_TRIAL_HOURS", 48)
INVOICING_ALLOW_LOCAL = env_bool("INVOICING_ALLOW_LOCAL", DEBUG and os.getenv("DURIELBIZ_DESKTOP") != "1")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "accounts:login"
LOGIN_URL = "accounts:login"
CSRF_FAILURE_VIEW = "pos_system.error_views.csrf_failure"
