from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

try:
    from apis.serializers import WhoAmISerializer  # reuse existing serializer
except Exception:  # pragma: no cover
    WhoAmISerializer = None


class MeV1View(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if WhoAmISerializer is None:
            return Response({"id": request.user.id, "email": request.user.email})
        return Response(WhoAmISerializer(request.user).data)

