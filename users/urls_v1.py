from django.urls import path

from .views_v1 import MeV1View

urlpatterns = [
    path("me/", MeV1View.as_view(), name="v1-users-me"),
]
