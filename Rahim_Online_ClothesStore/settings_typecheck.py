# Rahim_Online_ClothesStore/settings_typecheck.py
# Minimal typed shadow of runtime settings used by mypy / django-stubs
from typing import List, Optional, Sequence

# Django basics
SECRET_KEY: str = "typecheck-secret"
DEBUG: bool = True
ALLOWED_HOSTS: Sequence[str] = ["localhost"]

# Channels / ASGI
CHANNELS_ALLOWED_ORIGINS: Optional[List[str]] = None

# Geo / external keys that mypy complained about
GEOAPIFY_API_KEY: Optional[str] = None
GEOCODING_TIMEOUT: int = 10
GEOCODING_USER_AGENT: str = "rahim-typecheck-agent"

# Storage / static
STATIC_URL: str = "/static/"

# Any other keys you saw in errors: add them here with the expected type
SITE_DOMAIN: Optional[str] = None
# Payment placeholders for typechecking
PAYSTACK_PUBLIC_KEY: Optional[str] = None
PAYSTACK_SECRET_KEY: Optional[str] = None
STRIPE_PUBLIC_KEY: Optional[str] = None
STRIPE_SECRET_KEY: Optional[str] = None
STRIPE_WEBHOOK_SECRET: Optional[str] = None

# Add any additional constants you saw missing in the mypy output:
# e.g. things like DEFAULT_FROM_EMAIL: str = "..."
