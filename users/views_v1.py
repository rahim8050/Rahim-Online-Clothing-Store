from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema

try:
    from apis.serializers import WhoAmISerializer as _WhoAmISerializer  # reuse existing serializer
except Exception:  # pragma: no cover
    class _WhoAmISerializer(serializers.Serializer):  # minimal fallback for docs
        id = serializers.IntegerField()
        email = serializers.EmailField(allow_null=True, required=False)


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

