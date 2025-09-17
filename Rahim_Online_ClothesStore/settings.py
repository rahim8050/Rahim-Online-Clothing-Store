"""

Unified settings for Rahim_Online_ClothesStore
- Local dev: DEBUG=True (default), sqlite, http origins for 127.0.0.1/localhost
- Render prod: DEBUG=False, Postgres via DATABASE_URL (+sslmode=require), Redis Channels, HTTPS security, WhiteNoise

Production settings for Rahim_Online_ClothesStore (Render).

"""
from pathlib import Path
from datetime import timedelta

import dj_database_url
from django.contrib import messages
from django.db.models import CharField
from csp.constants import SELF, NONCE
from django.db.models.functions import Length  # for CharField lookup

import os
from django.core.management.utils import get_random_secret_key
import environ
import dj_database_url
from django.contrib import messages
from django.db import models


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else str(v).lower() in {"1", "true", "yes", "on"}

def env_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

DEBUG = env_bool("DEBUG", True)  # default True locally

# ---------------------------- Env -----------------------------
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


# Hosts
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost,codealpa-online-clothesstore.onrender.com",
)
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

# CSRF origins (http for local, https for all)
def build_csrf_origins(hosts: list[str]) -> list[str]:
    origins: list[str] = []
    for h in hosts:
        if h in {"127.0.0.1", "localhost"}:
            origins += [f"http://{h}:8000", f"http://{h}"]
        origins.append(f"https://{h}")
    # de-duplicate while preserving order
    return list(dict.fromkeys(origins))

CSRF_TRUSTED_ORIGINS = build_csrf_origins(ALLOWED_HOSTS)

# ------------------------ Hosts / CSRF ------------------------
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["codealpa-online-clothesstore.onrender.com"]
)

if DEBUG:
    ALLOWED_HOSTS += ["127.0.0.1", "localhost"]

# Helpful defaults for local development
if DEBUG:
    for h in ["127.0.0.1", "localhost", "[::1]"]:
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)


# Render dynamic hostname support
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)

def _with_scheme(host: str) -> str:
    return host if host.startswith(("http://", "https://")) else f"https://{host}"

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[_with_scheme(h) for h in ALLOWED_HOSTS]
)

if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["https://127.0.0.1:8000", "https://localhost:8000"]

if DEBUG:
    CORS_ALLOWED_ORIGINS = ["https://127.0.0.1:8000", "https://localhost:8000"]


ROOT_URLCONF = "Rahim_Online_ClothesStore.urls"
WSGI_APPLICATION = "Rahim_Online_ClothesStore.wsgi.application"
ASGI_APPLICATION = "Rahim_Online_ClothesStore.asgi.application"

# ------------------------ Applications ------------------------
INSTALLED_APPS = [
    "daphne",  # runserver alternative & ASGI server hooks

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "channels",

    "rest_framework",
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",
    "django_extensions",
    "csp",

    # your apps

    "csp",  # <-- CSP v4

    "product_app",
    "cart.apps.CartConfig",
    "orders.apps.OrdersConfig",
    "users.apps.UsersConfig",
    "utilities",
    "apis.apps.ApisConfig",
    "payments.apps.PaymentsConfig",

    # mpesa integrations
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

]

  

 

CONTENT_SECURITY_POLICY = {
    # Optional: don't send CSP headers on specific paths
    # "EXCLUDE_URL_PREFIXES": ["/admin"],

    "DIRECTIVES": {
        # Baseline
        "default-src": [SELF],

        # WebSockets for Channels/Daphne
        "connect-src": [SELF, "ws:", "wss:"],

        # Scripts: local + nonced inline + CDNs you use
        "script-src": [
            SELF,
            NONCE,                         # allow your small inline bootstraps with a nonce
            "https://unpkg.com",           # Leaflet CDN
            "https://js.stripe.com",       # Stripe.js (if used)
            "https://*.stripe.com",
            "https://js.paystack.co",      # Paystack inline
            "https://*.paystack.co",
            "https://*.paystack.com",
        ],

        # Styles: local + Leaflet + (optional) Google Fonts CSS
        "style-src": [
            SELF,
            "https://unpkg.com",
            "https://fonts.googleapis.com",
        ],

        # Fonts (if you use Google Fonts)
        "font-src": [SELF, "https://fonts.gstatic.com", "data:"],

        # Images: local + data/blob + OSM tiles
        "img-src": [
            SELF,
            "data:",
            "blob:",
            "https://tile.openstreetmap.org",
            "https://*.tile.openstreetmap.org",
        ],

        # Payment iframes/popups
        "frame-src": [
            "https://js.stripe.com",
            "https://*.stripe.com",
            "https://js.paystack.co",
            "https://*.paystack.co",
            "https://*.paystack.com",
        ],

        # Workers (if you use any blob workers)
        "worker-src": [SELF, "blob:"],

        # Click-jacking protection (only allow your own pages to frame yours)
        "frame-ancestors": [SELF],
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",  # static in dev/prod

    "csp.middleware.CSPMiddleware",            # CSP early
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

# Optional CORS (if installed)
try:

    import corsheaders  # noqa: F401
    INSTALLED_APPS += ["corsheaders"]
    # place CORS high, before CommonMiddleware
    MIDDLEWARE.insert(3, "corsheaders.middleware.CorsMiddleware")
except Exception:
    pass

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

# sqlite for dev by default; Postgres via DATABASE_URL for prod
db_default = dj_database_url.config(
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600,
    ssl_require=False,  # we add sslmode=require below when appropriate
)

engine = (db_default.get("ENGINE") or "").lower()
if not DEBUG and engine.endswith(("postgresql", "postgresql_psycopg2")):
    opts = db_default.get("OPTIONS") or {}
    opts.setdefault("sslmode", "require")
    db_default["OPTIONS"] = opts
else:
    # avoid OPTIONS on sqlite
    db_default.pop("OPTIONS", None)

DATABASES = {"default": db_default}

# -------------------------- Channels --------------------------
REDIS_URL = os.getenv("REDIS_URL")
if not DEBUG and not REDIS_URL:
    raise RuntimeError("REDIS_URL must be set in production for Channels.")

CHANNEL_LAYERS = {
    "default": (
        {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}
        if REDIS_URL
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    )
}

# ------------------------- Auth / API -------------------------
AUTH_USER_MODEL = "users.CustomUser"

AUTHENTICATION_BACKENDS = [
    "users.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",

        conn_max_age=600,
        ssl_require=IS_PROD,
    )
}

# -------------------------- Sessions --------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"



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

USE_REDIS = bool(REDIS_URL)
REDIS_SSL = bool(REDIS_URL) and REDIS_URL.startswith("rediss://")


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
    # Dev-only fallback
    from channels.layers import InMemoryChannelLayer  # noqa
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# --------------------------- Caches ---------------------------
if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,  # use rediss://... for SSL if needed
            "TIMEOUT": None,
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





# --------------------- Static & Media (Django 5) --------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]  # if you keep extra assets here

# --------------------- Static & Media (WhiteNoise) ------------
# Use an absolute prefix so template {% static %} resolves to /static/... and not a relative path
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


# WhiteNoise storages (Manifest in prod to fingerprint assets)
STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
    # Default media storage (FileSystem locally; optional cloud in prod)
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# Optional: switch media to Cloudinary automatically in prod if CLOUDINARY_URL is set
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
if CLOUDINARY_URL and not DEBUG:
    STORAGES["default"] = {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"
    }

# -------------------------- Security --------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = 60 * 60 * 24 * 14 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Ensure Whitenoise uses finders in development so /static/* is served
# directly from app/static and STATICFILES_DIRS without collectstatic.
if not IS_PROD:
    WHITENOISE_USE_FINDERS = True

# -------------------------- Security --------------------------
SECURE_SSL_REDIRECT = IS_PROD
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PROD else None
USE_X_FORWARDED_HOST = IS_PROD

SECURE_HSTS_SECONDS = (60 * 60 * 24 * 14) if IS_PROD else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PROD
SECURE_HSTS_PRELOAD = IS_PROD

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
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


MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
MPESA_EXPRESS_SHORTCODE = os.getenv("MPESA_EXPRESS_SHORTCODE")
MPESA_SHORTCODE_TYPE = os.getenv("MPESA_SHORTCODE_TYPE", "paybill")
MPESA_PASSKEY = os.getenv("MPESA_PASS_KEY")  # keep env name as used in your project

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

PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default=None)
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default=None)
PAYPAL_MODE = env("PAYPAL_MODE", default="sandbox")

# Paystack (required in prod)
PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY", default=None)
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", default=None)
if IS_PROD:
    missing = [k for k, v in {
        "PAYSTACK_PUBLIC_KEY": PAYSTACK_PUBLIC_KEY,
        "PAYSTACK_SECRET_KEY": PAYSTACK_SECRET_KEY,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required Paystack envs: {', '.join(missing)}")

if DEBUG:
    print("PAYSTACK_PUBLIC_KEY:", (PAYSTACK_PUBLIC_KEY or "")[:6], "…")
    print("PAYSTACK_SECRET_KEY:", (PAYSTACK_SECRET_KEY or "")[:6], "…")

# ---------------------------- Email ----------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else str(v).lower() in {"1", "true", "yes", "on"}

def _env_str(key: str, default: str = "") -> str:
    v = os.getenv(key, default)
    return (v or "").strip().strip('"').strip("'")

EMAIL_BACKEND = _env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = _env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False

EMAIL_HOST_USER = _env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _env_str("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@codealpa.shop")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[CodeAlpa] ")

_admins = os.getenv("DJANGO_ADMINS", "")
ADMINS = [tuple(item.split(":", 1)) for item in _admins.split(",") if ":" in item]


_default_from = _env_str("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "no-reply@codealpa.shop"
DEFAULT_FROM_EMAIL = _default_from
SERVER_EMAIL = _env_str("SERVER_EMAIL") or DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = _env_str("EMAIL_SUBJECT_PREFIX", "[CodeAlpa] ")


if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if IS_PROD and EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    missing = []
    if not EMAIL_HOST_USER:
        missing.append("EMAIL_HOST_USER")
    if not EMAIL_HOST_PASSWORD:
        missing.append("EMAIL_HOST_PASSWORD")
    if missing:
        raise RuntimeError(f"Missing required email envs: {', '.join(missing)}")

# ------------------------------ CSP ---------------------------
# CSP v4 format
from csp.constants import SELF, NONCE

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "connect-src": [SELF, "ws:", "wss:", "https://api.cloudinary.com"],
        "script-src": [
            SELF,
            NONCE,
            "https://cdn.tailwindcss.com",
            "https://cdn.jsdelivr.net",
            "https://unpkg.com",
            "https://widget.cloudinary.com",
            "https://js.stripe.com",
            "https://*.stripe.com",
            "https://js.paystack.co",
            "https://*.paystack.co",
            "https://*.paystack.com",
        ],
        # Allow external stylesheets as before and permit nonced <style> tags.
        # Inline style attributes remain blocked by default; see style-src-attr below.
        "style-src": [
            SELF,
            NONCE,
            "https://cdnjs.cloudflare.com",
            "https://unpkg.com",
            "https://fonts.googleapis.com",
        ],
        # Permit style attributes set by trusted JS (e.g., Leaflet, minor UI tweaks)
        # without allowing arbitrary <style> elements.
        "style-src-attr": [
            "'unsafe-inline'",
        ],
        "font-src": [SELF, "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "data:"],
        "img-src": [
            SELF,
            "data:", "blob:",
            "https://res.cloudinary.com",
            "https://tile.openstreetmap.org",
            "https://*.tile.openstreetmap.org",
        ],
        "frame-src": [
            "https://js.stripe.com",
            "https://*.stripe.com",
            "https://js.paystack.co",
            "https://*.paystack.co",
            "https://*.paystack.com",
        ],
        "worker-src": [SELF, "blob:"],
        "frame-ancestors": [SELF],
    },
}

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

CharField.register_lookup(Length)

from django.db.models.functions import Length  # noqa: E402
models.CharField.register_lookup(Length)

# ---------------------- OpenAPI (v1) -----------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Rahim Online Clothing Store API",
    "DESCRIPTION": "Versioned DRF API for catalog, cart, orders, payments, and users.",
    "VERSION": "1.0.0",
}

