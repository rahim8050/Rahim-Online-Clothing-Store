from django.apps import AppConfig
from django.db.backends.signals import connection_created

def _force_mysql_utc(sender, connection, **kwargs):
    if connection.vendor == "mysql":
        with connection.cursor() as c:
            # Force UTC offset so MySQL does not need TZ tables
            c.execute("SET time_zone = '+00:00'")
            # And strict mode to avoid zero-dates going forward
            c.execute("SET sql_mode = 'STRICT_TRANS_TABLES'")

class CoreConfig(AppConfig):
    name = "core"
    def ready(self):
        connection_created.connect(_force_mysql_utc)
