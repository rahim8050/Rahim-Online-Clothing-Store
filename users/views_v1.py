from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.serializers import WhoAmISerializer as _WhoAmISerializer


class MeV1View(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = _WhoAmISerializer

    @extend_schema(request=None, responses=_WhoAmISerializer)
    def get(self, request):
        try:
            # primary path
            return Response(_WhoAmISerializer(request.user).data)
        except Exception:
            # fallback shape
            return Response({"id": request.user.id, "email": request.user.email})
