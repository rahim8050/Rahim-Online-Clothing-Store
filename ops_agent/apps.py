# ──────────────────────────────────────────────────────────────────────────────
# ops_agent/apps.py
# ──────────────────────────────────────────────────────────────────────────────
from django.apps import AppConfig


class OpsAgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ops_agent"
    verbose_name = "Operations Agent"
