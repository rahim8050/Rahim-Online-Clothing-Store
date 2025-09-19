"""
Production settings for Rahim_Online_ClothesStore (Render).
"""

from pathlib import Path
from datetime import timedelta
import os

from django.core.management.utils import get_random_secret_key
import environ
import dj_database_url
from django.contrib import messages
from django.db import models
from django.db.models.functions import Length

# ---------------------------------------------------------------------
# Paths / env
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DEBUG", False)
ENV = env("ENV", default=("prod" if not DEBUG else "dev")).lower()
IS_PROD = not DEBUG

SECRET_KEY = env("SECRET_KEY", default=None)
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-" + get_random_secret_key()
    else:
        raise RuntimeError("SECRET_KEY is not set in environment.")

# ---------------------------------------------------------------------
# Hosts / CSRF / CORS
# ---------------------------------------------------------------------
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["codealpa-online-clothesstore.onrender.com"])
if DEBUG:
    ALLOWED_HOSTS += ["127.0.0.1", "localhost", "[::1]"]

# Render dynamic hostname
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

REQUIRED_HOSTS = ["127.0.0.1", "localhost", "[::1]", "codealpa-online-clothesstore.onrender.com"]
for _host in REQUIRED_HOSTS:
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

def _with_scheme(host: str) -> str:
    return host if host.startswith(("http://", "https://")) else f"https://{host}"

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[_with_scheme(h) for h in ALLOWED_HOSTS])
if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["https://127.0.0.1:8000", "https://localhost:8000"]

REQUIRED_CSRF_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000", "https://codealpa-online-clothesstore.onrender.com"]
for _origin in REQUIRED_CSRF_ORIGINS:
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)

# CORS (optional, only if you install `django-cors-headers`)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = DEBUG  # dev convenience; keep False in prod unless you mean it

# ---------------------------------------------------------------------
# Core Django plumbing
# ---------------------------------------------------------------------
ROOT_URLCONF = "Rahim_Online_ClothesStore.urls"
WSGI_APPLICATION = "Rahim_Online_ClothesStore.wsgi.application"
ASGI_APPLICATION = "Rahim_Online_ClothesStore.asgi.application"

INSTALLED_APPS = [
    # ASGI server
    "daphne",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",

    # Third-party
    "channels",
    "csp",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "django_extensions",
    "widget_tweaks",
    "django_daraja",  # M-Pesa SDK
    # "corsheaders",  # <- auto-added below if importable

    # First-party apps
    "users.apps.UsersConfig",
    "core",
    "assistant",
    "utilities",
    "product_app",
    "cart.apps.CartConfig",
    "Mpesa",
    
    "orders.apps.OrdersConfig",
    "payments.apps.PaymentsConfig",
    "apis.apps.ApisConfig",
    "dashboards",
    "notifications",
    "vendor_app",
    "invoicing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # CSP early
    "csp.middleware.CSPMiddleware",

    # Static
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # Standard Django stack
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Custom
    "core.middleware.PermissionsPolicyMiddleware",
    "core.middleware.RequestIDMiddleware",
    "cart.middleware.ClearGuestCookieOnLoginMiddleware",
]

# If corsheaders is installed, add it dynamically (works in both dev/prod)
try:
    import corsheaders  # noqa: F401
except Exception:
    corsheaders = None

if corsheaders:
    if "corsheaders" not in INSTALLED_APPS:
        INSTALLED_APPS.insert(INSTALLED_APPS.index("channels"), "corsheaders")
    if "corsheaders.middleware.CorsMiddleware" not in MIDDLEWARE:
        # Place high (after SecurityMiddleware) and before CommonMiddleware
        MIDDLEWARE.insert(1, "corsheaders.middleware.CorsMiddleware")

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

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
# settings.py (production)
from environ import Env

env = Env()

DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL"),
        conn_max_age=600,     # ok for direct
        ssl_require=True,
    )
}

DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"].update({
    "sslmode": "require",
})
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = False

# In-tests: in-memory sqlite
if os.environ.get("PYTEST_CURRENT_TEST"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# ---------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"

# ---------------------------------------------------------------------
# Channels (Redis)
# ---------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="")
USE_REDIS = bool(REDIS_URL)
REDIS_SSL = REDIS_URL.startswith("rediss://") if REDIS_URL else False

if IS_PROD and not USE_REDIS:
    raise RuntimeError("REDIS_URL is required in production for Channels & cache.")

if USE_REDIS:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ---------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------
if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": None,
            "OPTIONS": {"ssl": True} if REDIS_SSL else {},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "rahim-local",
            "TIMEOUT": None,
        }
    }

# Optional override to force Redis cache (even if not using channel layer)
USE_REDIS_CACHE = env.bool("USE_REDIS_CACHE", default=False)
if USE_REDIS_CACHE and REDIS_URL:
    _cache_opts = {"ssl": True} if REDIS_SSL else {}
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": None,
            "OPTIONS": _cache_opts,
        }
    }


# ---------------------------------------------------------------------
# DRF / Auth
# ---------------------------------------------------------------------

# ------------------------ Feature Flags ------------------------
# Default on in DEBUG, off otherwise unless explicitly enabled via env.
ETIMS_ENABLED = env.bool("ETIMS_ENABLED", default=bool(DEBUG))
KPIS_ENABLED = env.bool("KPIS_ENABLED", default=bool(DEBUG))

# ------------------------ Celery Beat --------------------------
# Schedule daily Vendor KPI aggregation at 00:30 Africa/Nairobi
try:
    from celery.schedules import crontab  # type: ignore
    _kpi_schedule = crontab(minute=30, hour=0)
except Exception:  # pragma: no cover
    _kpi_schedule = 24 * 60 * 60  # fallback: every 24h

CELERY_TIMEZONE = "Africa/Nairobi"
CELERY_BEAT_SCHEDULE = {
    "vendor-kpis-daily": {
        "task": "vendor_app.tasks.aggregate_kpis_daily_all",
        "schedule": _kpi_schedule,
        "options": {"queue": "default"},
    }
}
# ------------------------- Auth / API -------------------------

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.HMACAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "120/min"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

AUTH_USER_MODEL = "users.CustomUser"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
SITE_ID = int(os.getenv('SITE_ID', 1))
SITE_DOMAIN = os.getenv('SITE_DOMAIN', '127.0.0.1:8000')
SITE_SCHEME = os.getenv('SITE_SCHEME', 'https' if IS_PROD else 'http')
SITE_NAME = os.getenv('SITE_NAME', 'Rahim Online Shop')

LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------
# I18N / Time
# ---------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"   # App display timezone
USE_I18N = True
USE_TZ = True                  # DB stored in UTC

# ---------------------------------------------------------------------
# Static & Media (WhiteNoise)
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage" if IS_PROD
            else "whitenoise.storage.CompressedStaticFilesStorage"
        )
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

if not IS_PROD:
    WHITENOISE_USE_FINDERS = True

# ---------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------
SECURE_SSL_REDIRECT = IS_PROD
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PROD else None
USE_X_FORWARDED_HOST = IS_PROD

if IS_PROD:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 14
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------
# Payments & external
# ---------------------------------------------------------------------
# Geoapify
GEOAPIFY_API_KEY = env("GEOAPIFY_API_KEY", default=None)
GEOCODING_TIMEOUT = 6
GEOCODING_USER_AGENT = "RahimOnline/1.0 (contact: admin@example.com)"

# Stripe
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)
STRIPE_CURRENCY = env("STRIPE_CURRENCY", default="kes")

# PayPal
PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default=None)
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default=None)
PAYPAL_MODE = env("PAYPAL_MODE", default="sandbox")
PAYPAL_CURRENCY = env("PAYPAL_CURRENCY", default="USD")

# Paystack
PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY", default=None)
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", default=None)
PAYSTACK_CURRENCY = env("PAYSTACK_CURRENCY", default="KES")

if IS_PROD:
    missing = [k for k, v in {
        "PAYSTACK_PUBLIC_KEY": PAYSTACK_PUBLIC_KEY,
        "PAYSTACK_SECRET_KEY": PAYSTACK_SECRET_KEY,
        "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
        "STRIPE_WEBHOOK_SECRET": STRIPE_WEBHOOK_SECRET,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required payment envs: {', '.join(missing)}")

if DEBUG:
    for label, val in {
        "PAYSTACK_PUBLIC_KEY": PAYSTACK_PUBLIC_KEY,
        "PAYSTACK_SECRET_KEY": PAYSTACK_SECRET_KEY,
        "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
        "STRIPE_WEBHOOK_SECRET": STRIPE_WEBHOOK_SECRET,
    }.items():
        print(label + ":", (val or "")[:6], "…")

# M-Pesa
MPESA_ENVIRONMENT = env("MPESA_ENVIRONMENT", default="sandbox")
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default=None)
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default=None)
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default=None)
MPESA_EXPRESS_SHORTCODE = env("MPESA_EXPRESS_SHORTCODE", default=None)
MPESA_SHORTCODE_TYPE = env("MPESA_SHORTCODE_TYPE", default="paybill")
MPESA_PASSKEY = env("MPESA_PASS_KEY", default=None)

# ---------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else str(v).lower() in {"1", "true", "yes", "on"}

def _env_str(key: str, default: str = "") -> str:
    v = os.getenv(key, default)
    return (v or "").strip().strip('"').strip("'")

EMAIL_BACKEND = _env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = _env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", not EMAIL_USE_SSL)

EMAIL_HOST_USER = _env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _env_str("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

DEFAULT_FROM_EMAIL = _env_str("DEFAULT_FROM_EMAIL", f"no-reply@{SITE_DOMAIN.split(':')[0]}")
SUPPORT_EMAIL = _env_str("SUPPORT_EMAIL", f"support@{SITE_DOMAIN.split(':')[0]}")
SERVER_EMAIL = _env_str("SERVER_EMAIL") or DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = _env_str("EMAIL_SUBJECT_PREFIX", "[Rahim Online] ")

if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
if IS_PROD and EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    need = [k for k in ("EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD") if not globals().get(k)]
    if need:
        raise RuntimeError(f"Missing required email envs: {', '.join(need)}")

# ---------------------------------------------------------------------
# CSP (django-csp)
# ---------------------------------------------------------------------
# settings.py
from csp.constants import SELF, NONCE  # plus NONE/STRICT_DYNAMIC if you need them

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "connect-src": [SELF, "ws:", "wss:", "https://api.cloudinary.com"],
        "font-src": [SELF, "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "data:"],
        "frame-ancestors": [SELF],
        "frame-src": [
            "https://js.stripe.com", "https://*.stripe.com",
            "https://js.paystack.co", "https://*.paystack.co", "https://*.paystack.com",
        ],
        "img-src": [
            SELF, "data:", "blob:",
            "https://res.cloudinary.com",
            "https://tile.openstreetmap.org", "https://*.tile.openstreetmap.org",
        ],
        "script-src": [
            SELF, NONCE,
            "https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net", "https://unpkg.com",
            "https://widget.cloudinary.com",
            "https://js.stripe.com", "https://*.stripe.com",
            "https://js.paystack.co", "https://*.paystack.co", "https://*.paystack.com",
        ],
        "style-src": [SELF, NONCE, "https://cdnjs.cloudflare.com", "https://unpkg.com", "https://fonts.googleapis.com"],
        # keep this only if you truly need inline style attributes:
        "style-src-attr": ["'unsafe-inline'"],
        "worker-src": [SELF, "blob:"],
    },
}


# ---------------------------------------------------------------------
# UI / Misc
# ---------------------------------------------------------------------
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
        "payments": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
models.CharField.register_lookup(Length)

# ---------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Rahim Online Clothing Store API",
    "DESCRIPTION": "Versioned DRF API for catalog, cart, orders, payments, and users.",
    "VERSION": "1.0.0",
    # Disambiguate enums with the same field name across components
    "ENUM_NAME_OVERRIDES": {
        # Use fully qualified module paths and unify identical choice sets
        # Model fields
        "orders.models.Delivery.status": "DeliveryStatusEnum",
        "users.models.VendorApplication.status": "VendorApplicationStatusEnum",
        "orders.models.OrderItem.delivery_status": "OrderItemDeliveryStatusEnum",
        "orders.models.Order.payment_status": "OrderPaymentStatusEnum",
        # Serializer field uses the same choices as Delivery.status, keep same name
        "apis.serializers.DeliveryStatusSerializer.status": "DeliveryStatusEnum",
    },
}

# DRF: schema + throttle scopes (view-specific throttles)
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        # used by vendor_app.throttling.VendorOrgScopedRateThrottle
        "vendor.org": "60/min",
    },
}

