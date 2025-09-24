import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

import django


def main() -> None:
    django.setup()
    from core.models import AuditLog

    print("OK", AuditLog._meta.label)


if __name__ == "__main__":
    main()
