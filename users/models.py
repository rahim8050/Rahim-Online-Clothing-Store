from django.contrib.auth.models import AbstractUser
from django.db import models



# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, max_length=191)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_member = models.BooleanField(default=True)
    def __str__(self):
        return self.username
