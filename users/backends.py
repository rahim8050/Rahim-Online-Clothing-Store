from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

UserModel = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        users = UserModel.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        )
        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
