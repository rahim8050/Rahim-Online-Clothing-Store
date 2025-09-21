from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "users"

    def ready(self):
        _ = __import__("users.signals")
        # print("Users app is ready and signals are imported.")
