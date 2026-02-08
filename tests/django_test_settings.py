from channels.routing import ProtocolTypeRouter
from pathlib import Path

SECRET_KEY = "test-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]
BASE_DIR = Path(__file__).resolve().parents[1]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "channels",
    "rest_framework",
    "drf_spectacular",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_filters",
    "widget_tweaks",
    "django_extensions",
    "django_daraja",
    "invoicing.apps.InvoicingConfig",
    "cart.apps.CartConfig",
    "users.apps.UsersConfig",
    "product_app",
    "orders",
    "payments",
    "core",
    "apis.apps.ApisConfig",
    "dashboards",
    "assistant",
    "Mpesa",
    "utilities",
    "vendor_app",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

ROOT_URLCONF = "Rahim_Online_ClothesStore.urls"
ASGI_APPLICATION = __name__ + ".application"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"


application = ProtocolTypeRouter({})

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

# Avoid DB-bound auth lookup in websocket tests (AuthMiddlewareStack)
try:  # pragma: no cover - test settings only
    from channels import auth as channels_auth
    from channels import consumer as channels_consumer

    class _AnonUser:
        is_authenticated = False
        pk = None

    async def _test_get_user(scope):
        return _AnonUser()

    channels_auth.get_user = _test_get_user

    # Use a no-op AuthMiddlewareStack to avoid DB/session lookups in tests
    def _noop_auth_stack(inner):
        return inner

    channels_auth.AuthMiddlewareStack = _noop_auth_stack

    async def _noop_aclose_old_connections():
        return None

    channels_consumer.aclose_old_connections = _noop_aclose_old_connections
except Exception:
    pass

# URL patterns are defined in tests/test_urls.py to avoid early app import.
# Minimal spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Test API",
    "DESCRIPTION": "Test schema",
    "VERSION": "1.0.0",
}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "vendor.org": "100/min",
        "invoice.export": "20/min",
    },
}

# Use the project's custom user model to avoid M2M mismatches in tests
AUTH_USER_MODEL = "users.CustomUser"
SITE_ID = 1
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

# Crispy (minimal)
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
