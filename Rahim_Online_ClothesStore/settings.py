"""
Production settings for Rahim_Online_ClothesStore (Render).
"""

# ---------------------------- Core ----------------------------
from pathlib import Path
import os
from datetime import timedelta

import environ
import dj_database_url
from django.contrib import messages
from django.db import models

BASE_DIR = Path(__file__).resolve().parent.parent

# Single source of truth for env vars
env = environ.Env(DEBUG=(bool, False))
# Locally this reads .env; on Render you use dashboard env vars (safe to keep here)
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DEBUG", False)

SECRET_KEY = env("SECRET_KEY", default=None)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set in environment.")

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["codealpa-online-clothesstore.onrender.com"]
)

# Helpful defaults for local development
if DEBUG:
    for h in ["127.0.0.1", "localhost", "[::1]"]:
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)

# Render dynamic hostname support
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# CSRF needs absolute origins with scheme
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[f"https://{h}" if not h.startswith(("http://", "https://")) else h for h in ALLOWED_HOSTS]
)

ROOT_URLCONF = "Rahim_Online_ClothesStore.urls"
ASGI_APPLICATION = "Rahim_Online_ClothesStore.asgi.application"

# ------------------------ Applications ------------------------
INSTALLED_APPS = [
    "daphne",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "channels",
    "product_app",
    "cart.apps.CartConfig",
    "orders.apps.OrdersConfig",
    "crispy_forms",
    "crispy_bootstrap5",
    "users.apps.UsersConfig",
    "widget_tweaks",
    "django_daraja",
    "Mpesa",
    "utilities",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apis.apps.ApisConfig",
    "dashboards",
    "django_extensions",
    "payments",
    "assistant",
    "core",
    "notifications",
    "vendor_app",
    "invoicing",
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
    "core.middleware.PermissionsPolicyMiddleware",
    "core.middleware.RequestIDMiddleware",
]

try:
    import corsheaders  # noqa
except ImportError:  # pragma: no cover
    corsheaders = None

if corsheaders:
    if "corsheaders" not in INSTALLED_APPS:
        INSTALLED_APPS += ["corsheaders"]
    # place high in stack right after SecurityMiddleware (index 0)
    if "corsheaders.middleware.CorsMiddleware" not in MIDDLEWARE:
        MIDDLEWARE.insert(1, "corsheaders.middleware.CorsMiddleware")

# Always append guest cart cookie clearer near the end
if "cart.middleware.ClearGuestCookieOnLoginMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.append("cart.middleware.ClearGuestCookieOnLoginMiddleware")

AUTHENTICATION_BACKENDS = [
    "users.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ------------------------- Templates --------------------------
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

# -------------------------- Database --------------------------
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,          # keep connections warm
        ssl_require=not DEBUG,     # mainly affects Postgres; harmless otherwise
    )
}

# If env points to MySQL, add safe session settings (no tz tables needed)
if DATABASES["default"].get("ENGINE") == "django.db.backends.mysql":
    DATABASES["default"].setdefault("OPTIONS", {})
    # strict mode + keep DB session in UTC to bypass MySQL tz tables
    DATABASES["default"]["OPTIONS"].update({
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES', time_zone='+00:00'",
        "charset": "utf8mb4",
        "use_unicode": True,
    })
    # (optional) Django 4.2+: auto ping to avoid stale connections
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Use in-memory SQLite for pytest to avoid external DB deps
if os.environ.get("PYTEST_CURRENT_TEST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }


# -------------------------- Channels --------------------------
REDIS_URL = env("REDIS_URL", default="")
REDIS_SSL = bool(REDIS_URL) and REDIS_URL.startswith("rediss://")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "ssl": REDIS_SSL,
        },
    }
}

# Cache: prefer Redis only when explicitly enabled (prod), otherwise use local memory
USE_REDIS_CACHE = env.bool("USE_REDIS_CACHE", default=False)
if USE_REDIS_CACHE and REDIS_URL:
    _cache_options = {}
    if REDIS_SSL:
        # Only include the ssl flag for rediss:// URLs to avoid client kwarg errors
        _cache_options["ssl"] = True

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": None,
            "OPTIONS": _cache_options,
        }
    }
else:
    # Fallback: in‑memory cache (sufficient for local dev & throttling)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "rahim-local",
            "TIMEOUT": None,
        }
    }
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
# ------------------------- Auth / API -------------------------
REST_FRAMEWORK = {
    # Permissions: read for all, write for auth by default
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    # Auth: keep JWT + Session
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.HMACAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Filtering/search/order support
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Pagination
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Throttling
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "120/min",
    },
    # OpenAPI schema
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

AUTH_USER_MODEL = "users.CustomUser"

LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------ I18N / Time -------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC" 

# --------------------- Static & Media (WhiteNoise) ------------
# Use an absolute prefix so template {% static %} resolves to /static/... and not a relative path
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

# ------------------------ Security (prod) ---------------------
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# -------------------------- Security --------------------------
ENV = os.getenv("ENV", "dev").lower()     # dev | staging | prod
DEBUG = os.getenv("DEBUG", "1") == "1"
IS_PROD = ENV == "prod"

# --- Redirects / proxy trust ---
SECURE_SSL_REDIRECT = IS_PROD                # only force HTTPS in prod
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if IS_PROD else None
USE_X_FORWARDED_HOST = IS_PROD

# --- HSTS (never in dev) ---
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 14 if IS_PROD else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PROD
SECURE_HSTS_PRELOAD = IS_PROD

# --- Cookies (secure only when using HTTPS) ---
SESSION_COOKIE_SECURE = IS_PROD
CSRF_COOKIE_SECURE = IS_PROD
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Optional: set a canonical host in prod to avoid odd redirects
ALLOWED_HOSTS = ["127.0.0.1", "localhost"] if not IS_PROD else ["yourdomain.com"]

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# In dev allow any origin for rapid iteration
CORS_ALLOW_ALL_ORIGINS = True

# -------------------- Third-party / Payments -------------------
# Geoapify
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

# Stripe
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)

# PayPal
PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default=None)
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default=None)
PAYPAL_MODE = env("PAYPAL_MODE", default="sandbox")

# Paystack (✅ these are the ones you need)
PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY", default=None)
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", default=None)

# Fail fast in production if Paystack keys are missing
if not DEBUG:
    missing = [k for k, v in {
        "PAYSTACK_PUBLIC_KEY": PAYSTACK_PUBLIC_KEY,
        "PAYSTACK_SECRET_KEY": PAYSTACK_SECRET_KEY,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required Paystack envs: {', '.join(missing)}")

# Optional: short prefix logs in DEBUG only (remove after verifying)
if DEBUG:
    print("PAYSTACK_PUBLIC_KEY:", (PAYSTACK_PUBLIC_KEY or "")[:6], "…")
    print("PAYSTACK_SECRET_KEY:", (PAYSTACK_SECRET_KEY or "")[:6], "…")

# ---------------------------- Email ----------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else str(v).lower() in {"1", "true", "yes", "on"}

def _env_str(key: str, default: str = "") -> str:
    # Strip whitespace and surrounding quotes copied from dashboards
    v = os.getenv(key, default)
    return (v or "").strip().strip('"').strip("'")

EMAIL_BACKEND = _env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = _env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False  # never both

EMAIL_HOST_USER = _env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _env_str("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

# Prefer a branded From that matches the authenticated account
_default_from = _env_str("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "no-reply@codealpa.shop"
DEFAULT_FROM_EMAIL = _default_from
SERVER_EMAIL = _env_str("SERVER_EMAIL") or DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = _env_str("EMAIL_SUBJECT_PREFIX", "[CodeAlpa] ")

# In dev with no SMTP host, fall back to console backend
if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Fail fast in production if using SMTP without proper creds
if not DEBUG and EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    missing = []
    if not EMAIL_HOST_USER:
        missing.append("EMAIL_HOST_USER")
    if not EMAIL_HOST_PASSWORD:
        missing.append("EMAIL_HOST_PASSWORD")
    if missing:
        raise RuntimeError(f"Missing required email envs: {', '.join(missing)}")


# --------------------------- UI bits ---------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}

# --------------------------- Logging ---------------------------
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

# ---------------------------- Misc -----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
from django.db.models.functions import Length  # noqa: E402
models.CharField.register_lookup(Length)

# ---------------------- OpenAPI (v1) -----------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Rahim Online Clothing Store API",
    "DESCRIPTION": "Versioned DRF API for catalog, cart, orders, payments, and users.",
    "VERSION": "1.0.0",
    # Disambiguate enums with the same field name across components
    "ENUM_NAME_OVERRIDES": {
        # Model fields
        "orders.Delivery.status": "DeliveryStatusEnum",
        "users.VendorApplication.status": "VendorApplicationStatusEnum",
        "orders.OrderItem.delivery_status": "OrderItemDeliveryStatusEnum",
        "orders.Order.payment_status": "OrderPaymentStatusEnum",
        # Serializer fields (in case they are materialized as enums)
        "apis.serializers.DeliveryStatusSerializer.status": "DeliveryStatusBodyEnum",
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
