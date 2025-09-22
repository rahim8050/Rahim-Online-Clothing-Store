# Create your models here.
# notifications/models.py
from django.conf import settings
from django.db import models


class Notification(models.Model):
    LEVELS = (("info", "Info"), ("success", "Success"), ("warning", "Warning"), ("error", "Error"))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=10, choices=LEVELS, default="info")
    url = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
