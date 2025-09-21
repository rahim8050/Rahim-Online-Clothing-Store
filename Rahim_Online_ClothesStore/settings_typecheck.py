# Minimal settings used only by mypy's django-stubs plugin.
SECRET_KEY = "typecheck"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    # Add your local apps here if you want model type info:
    # "users", "orders", "payments", ...
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
