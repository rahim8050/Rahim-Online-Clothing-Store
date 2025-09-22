from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_v1 import MemberViewSet, OrgViewSet

router = DefaultRouter()
router.register(r"orgs", OrgViewSet, basename="vendor-orgs")
router.register(r"members", MemberViewSet, basename="vendor-members")

urlpatterns = [
    path("", include(router.urls)),
]
