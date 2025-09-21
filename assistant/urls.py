from django.urls import path

from .views import AskView

urlpatterns = [
    path("ask/", AskView.as_view(), name="assistant-ask"),
]
