SECRET_KEY = "test-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}

ROOT_URLCONF = 'tests.test_urls'
ASGI_APPLICATION = __name__ + ".application"

from channels.routing import ProtocolTypeRouter
application = ProtocolTypeRouter({})

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

# Crispy (minimal)
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
