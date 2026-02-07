from __future__ import annotations

from datetime import timedelta

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """JWT obtain with scoped throttling."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth.token"


class ThrottledTokenRefreshView(TokenRefreshView):
    """JWT refresh with scoped throttling."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth.refresh"


class SessionJWTExchangeView(APIView):
    """Issue a short-lived access token for an authenticated session user."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth.session_jwt"

    ACCESS_LIFETIME = timedelta(minutes=15)

    def post(self, request):
        refresh = RefreshToken.for_user(request.user)
        access = refresh.access_token
        access.set_exp(lifetime=self.ACCESS_LIFETIME)
        return Response(
            {
                "access": str(access),
                "expires_in": int(self.ACCESS_LIFETIME.total_seconds()),
                "token_type": "Bearer",
            }
        )
