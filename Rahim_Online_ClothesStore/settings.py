"""
Production settings for Rahim_Online_ClothesStore on Render.
"""

from pathlib import Path
import os

from datetime import timedelta
from urllib.parse import urlparse, parse_qs

from django.db import models
from django.db.models import CharField
from dotenv import load_dotenv
import environ
from datetime import timedelta
import dj_database_url


from urllib.parse import urlparse, parse_qs


# Load environment   variables from .env file
load_dotenv()
env = environ.Env()




import dj_database_url
from django.db import models
from django.db.models import CharField
from django.contrib import messages

# --------------------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# Env helpers
def env_bool(key: str, default=False):
    val = os.getenv(key)
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "yes", "on")

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "codealpa-online-clothesstore.onrender.com"]

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/
DEBUG = os.getenv("DEBUG", "0") == "1"

DATABASE_URL = os.getenv("DATABASE_URL")

def _db_from_url(url: str):
    p = urlparse(url)
    scheme = (p.scheme or "").lower()
    if scheme in {"postgres", "postgresql", "postgresql+psycopg", "postgis"}:
        engine = "django.db.backends.postgresql"
    elif scheme in {"sqlite", "sqlite3"}:
        engine = "django.db.backends.sqlite3"
    else:
        raise RuntimeError(f"Unsupported DB scheme: {scheme}")

    if engine.endswith("sqlite3"):
        name = p.path[1:] if p.path and p.path != "/" else (BASE_DIR / "db.sqlite3")
        return {"ENGINE": engine, "NAME": str(name)}

    q = {k: v[-1] for k, v in parse_qs(p.query).items()}
    opts = {}
    # Force SSL in prod unless disabled explicitly
    if not DEBUG and q.get("sslmode", "require"):
        opts["sslmode"] = q.get("sslmode", "require")

    return {
        "ENGINE": engine,
        "NAME": p.path.lstrip("/"),
        "USER": p.username or "",
        "PASSWORD": p.password or "",
        "HOST": p.hostname or "",
        "PORT": p.port or "",
        "OPTIONS": opts,
        "CONN_MAX_AGE": 600,
    }

if DATABASE_URL:
    DATABASES = {"default": _db_from_url(DATABASE_URL)}
else:


DATABASE_URL = os.getenv("DATABASE_URL")


if DATABASE_URL:
    # Postgres on Render
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    # Local fallback (no env var)

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }



# Debug line (safe to keep for now; remove later)
print("DB_CONFIG_DEBUG:", {
    "ENGINE": DATABASES["default"].get("ENGINE"),
    "NAME": DATABASES["default"].get("NAME"),
    "HAS_URL": bool(DATABASE_URL),
})


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')


# IMPORTANT: set this in Render → Environment
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fail closed in prod; relax this if you need to boot while wiring secrets
    raise RuntimeError("SECRET_KEY is not set in environment.")


# Your live domain here (keep localhost for local dev)
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,codealpa-online-clothesstore.onrender.com",
).split(",")

# SECURITY WARNING: don't run with debug turned on in production!




CSRF_TRUSTED_ORIGINS = [
    "https://codealpa-online-clothesstore.onrender.com",  # Render app URL
]

ROOT_URLCONF = "Rahim_Online_ClothesStore.urls"
ASGI_APPLICATION = "Rahim_Online_ClothesStore.asgi.application"

# --------------------------------------------------------------------------------------
# Apps
# --------------------------------------------------------------------------------------
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

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
    "apis.apps.ApisConfig",
    "django_extensions",
]

MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static in prod
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Must remain last to ensure geolocation is always disabled
    "core.middleware.PermissionsPolicyMiddleware",

    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Must remain last to ensure geolocation is always disabled
    'core.middleware.PermissionsPolicyMiddleware',
]
AUTHENTICATION_BACKENDS = [
    'users.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',

]

# --------------------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------------------
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


# --------------------------------------------------------------------------------------
# Database (Render Postgres via DATABASE_URL; local fallback sqlite)
# --------------------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=not DEBUG,  # Render prod → True
    )
}

# --------------------------------------------------------------------------------------
# Channels (Redis if REDIS_URL provided; else in-memory for dev)
# --------------------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL")
CHANNEL_LAYERS = {
    "default": (
        {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
        if REDIS_URL
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    )
}

ASGI_APPLICATION = "Rahim_Online_ClothesStore.asgi.application"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
# The Mpesa environment to use
# Possible values: sandbox, production

MPESA_ENVIRONMENT = 'sandbox'

# Credentials for the daraja app

MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET')


#Shortcode to use for transactions. For sandbox  use the Shortcode 1 provided on test credentials page

MPESA_SHORTCODE = os.environ.get('MPESA_SHORTCODE')

# Shortcode to use for Lipa na MPESA Online (MPESA Express) transactions
# This is only used on sandbox, do not set this variable in production
# For sandbox use the Lipa na MPESA Online Shorcode provided on test credentials page

MPESA_EXPRESS_SHORTCODE = os.environ.get('MPESA_EXPRESS_SHORTCODE')

# Type of shortcode
# Possible values:
# - paybill (For Paybill)
# - till_number (For Buy Goods Till Number)

MPESA_SHORTCODE_TYPE = 'paybill'

# Lipa na MPESA Online passkey
# Sandbox passkey is available on test credentials page
# Production passkey is sent via email once you go live

MPESA_PASSKEY = os.environ.get('MPESA_PASS_KEY')

# Stripe configuration
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


# PayPal configuration
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')

# Paystack configuration
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')


# Username for initiator (to be used in B2C, B2B, AccountBalance and TransactionStatusQuery Transactions)

MPESA_INITIATOR_USERNAME = 'initiator_username'

# Plaintext password for initiator (to be used in B2C, B2B, AccountBalance and TransactionStatusQuery Transactions)

MPESA_INITIATOR_SECURITY_CREDENTIAL = 'initiator_security_credential'
# Geopify settings
# API key is read from the environment; never expose to templates
GEOAPIFY_API_KEY = env("GEOAPIFY_API_KEY")
GEOCODING_TIMEOUT = 6
GEOCODING_USER_AGENT = 'RahimOnline/1.0 (contact: admin@example.com)'



# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases


# DATABASES = {
#     'default': {
#         'ENGINE': os.environ.get('ENGINE'),
#         'NAME': os.environ.get('NAME'),
#         'USER': os.environ.get('User'),
#         'PASSWORD': os.environ.get('PASSWORD'),
#         'HOST': os.environ.get('HOST'),
#         'PORT': os.environ.get('PORT'),
#         'OPTIONS': {
#             'charset': 'utf8mb4',
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         } if os.environ.get('ENGINE') == 'django.db.backends.mysql' else {},
#     }
# }

CHANNEL_LAYERS = {
    "default": (
        {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [os.environ.get("REDIS_URL")]},
        }
        if os.environ.get("REDIS_URL")
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    )
}






# --------------------------------------------------------------------------------------
# Auth / API
# --------------------------------------------------------------------------------------
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

AUTH_USER_MODEL = "users.CustomUser"

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
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]  # if you have app-level assets too

STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# --------------------------------------------------------------------------------------
# Security (prod)
# --------------------------------------------------------------------------------------
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG or True
CSRF_COOKIE_SECURE = not DEBUG or True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 14 if not DEBUG else 0  # 14 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# --------------------------------------------------------------------------------------
# Third-party keys (read softly from env)
# --------------------------------------------------------------------------------------
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GEOCODING_TIMEOUT = 6
GEOCODING_USER_AGENT = "RahimOnline/1.0 (contact: admin@example.com)"

# Payments
MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
MPESA_EXPRESS_SHORTCODE = os.getenv("MPESA_EXPRESS_SHORTCODE")
MPESA_SHORTCODE_TYPE = os.getenv("MPESA_SHORTCODE_TYPE", "paybill")
MPESA_PASSKEY = os.getenv("MPESA_PASS_KEY")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")

PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
# --------------------------------------------------------------------------------------
# Email (SMTP)
# --------------------------------------------------------------------------------------
def env_bool(key: str, default=False):
    val = os.getenv(key)
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "yes", "on")

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "")          # e.g. smtp.sendgrid.net or smtp.gmail.com
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))  # 587 for TLS, 465 for SSL
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_SSL:
    # Don’t use both at once; prefer TLS on 587 unless your provider requires SSL
    EMAIL_USE_TLS = False

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")        # SMTP username
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")# SMTP password / API key
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))     # seconds

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@codealpa.shop")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[CodeAlpa] ")

# Optional: send error emails to admins (set DJANGO_ADMINS="Name1:mail1,Name2:mail2")
_admins = os.getenv("DJANGO_ADMINS", "")
ADMINS = [tuple(item.split(":", 1)) for item in _admins.split(",") if ":" in item]

# DX: in local DEV with no SMTP creds, fall back to console backend
if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --------------------------------------------------------------------------------------
# Forms / UI
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

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "channels": {"handlers": ["console"], "level": "INFO"},
        "orders": {"handlers": ["console"], "level": "DEBUG"},
    },
}


# --------------------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CharField.register_lookup(models.functions.Length)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "channels": {"handlers": ["console"], "level": "INFO"},
        "orders": {"handlers": ["console"], "level": "DEBUG"},
    },
}


