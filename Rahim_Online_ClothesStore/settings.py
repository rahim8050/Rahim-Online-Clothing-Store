"""
Unified settings for Rahim_Online_ClothesStore
- Local dev: DEBUG=True (default), sqlite, http origins for 127.0.0.1/localhost
- Render prod: DEBUG=False, Postgres via DATABASE_URL (+sslmode=require), Redis Channels, HTTPS security, WhiteNoise
"""
from pathlib import Path
import os
from datetime import timedelta
import dj_database_url
from django.contrib import messages
from django.db.models import CharField
from django.db.models.functions import Length  # for CharField lookup

# ---------------------------- Core ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else str(v).lower() in {"1", "true", "yes", "on"}

def env_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

DEBUG = env_bool("DEBUG", True)  # default True locally

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
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

    "channels",
    "rest_framework",
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",
    "django_extensions",
    "csp",

    # your apps
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
]
CSP_DEFAULT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:", "blob:",
               "https://tile.openstreetmap.org", "https://*.tile.openstreetmap.org")
CSP_CONNECT_SRC = ("'self'", "ws:", "wss:")
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static in dev/prod
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.PermissionsPolicyMiddleware",
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

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

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

# --------------------- Static & Media (Django 5) --------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]  # if you keep extra assets here

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

# -------------------- Third-party / Payments -------------------
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GEOCODING_TIMEOUT = 6
GEOCODING_USER_AGENT = "RahimOnline/1.0 (contact: admin@example.com)"

MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
MPESA_EXPRESS_SHORTCODE = os.getenv("MPESA_EXPRESS_SHORTCODE")
MPESA_SHORTCODE_TYPE = os.getenv("MPESA_SHORTCODE_TYPE", "paybill")
MPESA_PASSKEY = os.getenv("MPESA_PASS_KEY")  # keep env name as used in your project

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")

PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# ---------------------------- Email ----------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@codealpa.shop")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[CodeAlpa] ")

_admins = os.getenv("DJANGO_ADMINS", "")
ADMINS = [tuple(item.split(":", 1)) for item in _admins.split(",") if ":" in item]

if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

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
