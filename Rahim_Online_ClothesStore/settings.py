"""
Unified settings for Rahim_Online_ClothesStore
- DEV (default): DEBUG=True, sqlite, InMemory Channels, permissive CORS.
- PROD (Render): DEBUG=False, Postgres via DATABASE_URL, Redis Channels, HTTPS security, WhiteNoise.
"""

from pathlib import Path
from datetime import timedelta
import os

import environ
import dj_database_url
from django.contrib import messages
from django.core.management.utils import get_random_secret_key
from django.db.models import CharField
from django.db.models.functions import Length
from csp.constants import SELF  # NOTE: django-csp has SELF/NONE; NOT NONCE

# --------------------------------------------------------------------------------------
# Base & helpers
# --------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else str(v).lower() in {"1", "true", "yes", "on"}

def env_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

# Load .env if present
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DEBUG", True)
IS_PROD = not DEBUG

# Secret key
SECRET_KEY = env("SECRET_KEY", default=None)
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-" + get_random_secret_key()
    else:
        raise RuntimeError("SECRET_KEY is not set in environment.")

# --------------------------------------------------------------------------------------
# Hosts / CSRF / CORS
# --------------------------------------------------------------------------------------
# Start with env-provided hosts; add Render runtime hostname if present
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "codealpa-online-clothesstore.onrender.com")
if DEBUG:
    ALLOWED_HOSTS += ["127.0.0.1", "localhost", "[::1]"]

RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

# CSRF origins: https://<host> for every allowed host
def _with_scheme(host: str) -> str:
    return host if host.startswith(("http://", "https://")) else f"https://{host}"
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    ",".join(_with_scheme(h) for h in ALLOWED_HOSTS if h),
)

# Optional CORS (auto-added only if package installed)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_ALL_ORIGINS = DEBUG

# --------------------------------------------------------------------------------------
# Django app plumbing
# --------------------------------------------------------------------------------------
ROOT_URLCONF = "Rahim_Online_ClothesStore.urls"
WSGI_APPLICATION = "Rahim_Online_ClothesStore.wsgi.application"
ASGI_APPLICATION = "Rahim_Online_ClothesStore.asgi.application"

INSTALLED_APPS = [
    "daphne",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # ASGI / APIs
    "channels",
    "rest_framework",
    "django_filters",
    "drf_spectacular",

    # Forms/UI
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",

    # Tools
    "django_extensions",
    "csp",

    # Your apps
    "product_app",
    "cart.apps.CartConfig",
    "orders.apps.OrdersConfig",
    "users.apps.UsersConfig",
    "utilities",
    "apis.apps.ApisConfig",
    "payments.apps.PaymentsConfig",
    "django_daraja",
    "Mpesa",
    "dashboards",
    "assistant",
    "core",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "core.middleware.PermissionsPolicyMiddleware",
    "core.middleware.RequestIDMiddleware",
]

# If corsheaders is installed, enable it high in the stack automatically
try:
    import corsheaders  # noqa: F401
    INSTALLED_APPS.append("corsheaders")
    if "corsheaders.middleware.CorsMiddleware" not in MIDDLEWARE:
        MIDDLEWARE.insert(1, "corsheaders.middleware.CorsMiddleware")
except Exception:
    pass

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
                "cart.context_processors.cart_counter",
                "assistant.context_processors.assistant_role",
            ],
        },
    },
]

# --------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=IS_PROD,
    )
}

# --------------------------------------------------------------------------------------
# Channels & Cache (Redis in prod, in-memory in dev)
# --------------------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "")
if IS_PROD and not REDIS_URL:
    raise RuntimeError("REDIS_URL is required in production for Channels & cache.")

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": None,
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "rahim-local",
            "TIMEOUT": None,
        }
    }

# --------------------------------------------------------------------------------------
# REST / Auth
# --------------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.HMACAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

AUTH_USER_MODEL = "users.CustomUser"
AUTHENTICATION_BACKENDS = [
    "users.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# --------------------------------------------------------------------------------------
# I18N / TZ
# --------------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------------------
# Static & Media (WhiteNoise)
# --------------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PROD
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# Optional Cloudinary media in prod if CLOUDINARY_URL is present
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
if CLOUDINARY_URL and IS_PROD:
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}

# --------------------------------------------------------------------------------------
# Security (prod)
# --------------------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if IS_PROD:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 14
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CONTENT_TYPE_NOSNIFF = True
else:
    # Helpful in dev for static finder behavior
    WHITENOISE_USE_FINDERS = True

# --------------------------------------------------------------------------------------
# Payments / 3rd party keys
# --------------------------------------------------------------------------------------
GEOAPIFY_API_KEY = env("GEOAPIFY_API_KEY", default=None)
GEOCODING_TIMEOUT = 6
GEOCODING_USER_AGENT = "RahimOnline/1.0 (contact: admin@example.com)"

# M-PESA
MPESA_ENVIRONMENT = env("MPESA_ENVIRONMENT", default="sandbox")
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default=None)
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default=None)
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default=None)
MPESA_EXPRESS_SHORTCODE = env("MPESA_EXPRESS_SHORTCODE", default=None)
MPESA_SHORTCODE_TYPE = env("MPESA_SHORTCODE_TYPE", default="paybill")
MPESA_PASSKEY = env("MPESA_PASS_KEY", default=None)

# Stripe / PayPal / Paystack
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)

PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default=None)
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default=None)
PAYPAL_MODE = env("PAYPAL_MODE", default="sandbox")

PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY", default=None)
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", default=None)
if IS_PROD and (not PAYSTACK_PUBLIC_KEY or not PAYSTACK_SECRET_KEY):
    raise RuntimeError("Missing required Paystack envs: PAYSTACK_PUBLIC_KEY, PAYSTACK_SECRET_KEY")

# --------------------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------------------
def _env_str(key: str, default: str = "") -> str:
    v = os.getenv(key, default)
    return (v or "").strip().strip('"').strip("'")

EMAIL_BACKEND = _env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = _env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False

EMAIL_HOST_USER = _env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _env_str("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

DEFAULT_FROM_EMAIL = _env_str("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "no-reply@codealpa.shop"
SERVER_EMAIL = _env_str("SERVER_EMAIL") or DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = _env_str("EMAIL_SUBJECT_PREFIX", "[CodeAlpa] ")

if IS_PROD and EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    missing = []
    if not EMAIL_HOST_USER:
        missing.append("EMAIL_HOST_USER")
    if not EMAIL_HOST_PASSWORD:
        missing.append("EMAIL_HOST_PASSWORD")
    if missing:
        raise RuntimeError(f"Missing required email envs: {', '.join(missing)}")

# --------------------------------------------------------------------------------------
# CSP (temporary inline allow to unblock; switch to nonces later)
# --------------------------------------------------------------------------------------
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "connect-src": [SELF, "ws:", "wss:", "https://api.cloudinary.com"],
        "script-src": [
            SELF, "'unsafe-inline'",
            "https://cdn.tailwindcss.com",
            "https://cdn.jsdelivr.net",
            "https://unpkg.com",
            "https://widget.cloudinary.com",
            "https://js.stripe.com", "https://*.stripe.com",
            "https://js.paystack.co", "https://*.paystack.co", "https://*.paystack.com",
        ],
        "style-src": [
            SELF, "'unsafe-inline'",
            "https://cdnjs.cloudflare.com",
            "https://unpkg.com",
            "https://fonts.googleapis.com",
        ],
        "font-src": [SELF, "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "data:"],
        "img-src": [
            SELF, "data:", "blob:",
            "https://res.cloudinary.com",
            "https://tile.openstreetmap.org", "https://*.tile.openstreetmap.org",
        ],
        "frame-src": [
            "https://js.stripe.com", "https://*.stripe.com",
            "https://js.paystack.co", "https://*.paystack.co", "https://*.paystack.com",
        ],
        "worker-src": [SELF, "blob:"],
        "frame-ancestors": [SELF],
    },
}

# --------------------------------------------------------------------------------------
# UI tweaks / logging
# --------------------------------------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "channels": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "orders": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CharField.register_lookup(Length)
