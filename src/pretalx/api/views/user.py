from rest_framework.response import Response
from rest_framework.views import APIView


class MeView(APIView):
    def get(self, request, **kwargs):
        return Response(
            {
                'email': getattr(request.user, 'email', None),
                'name': getattr(request.user, 'name', None),
                'locale': getattr(request.user, 'locale', None),
                'timezone': getattr(request.user, 'timezone', None),
            }
        )
