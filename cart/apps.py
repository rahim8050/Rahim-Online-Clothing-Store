from django.apps import AppConfig
import logging
logger = logging.getLogger(__name__)


class CartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cart"

    def ready(self):
        # Register signal handlers (login merge)
        try:  # pragma: no cover
            import cart.signals  # noqa: F401
        except ModuleNotFoundError as e:
           logger.debug("cart.signals not available: %s", e)
