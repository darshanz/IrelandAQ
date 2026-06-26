from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer


@api_view(['GET'])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
def health_check(request):
    return Response({'status':'ok'})
