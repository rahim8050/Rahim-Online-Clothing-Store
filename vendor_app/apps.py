from django.apps import AppConfig


class VendorAppConfig(AppConfig):
    name = "vendor_app"
    verbose_name = "Vendors & Tenancy"

    def ready(self) -> None:  # noqa: D401
        """Hook for signals in the future (none for now)."""
        # from . import signals  # noqa: F401
        return super().ready()
