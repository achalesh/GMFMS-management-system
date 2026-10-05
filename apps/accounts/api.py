from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import HasDashboardAccess


class CurrentUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    display_name = serializers.CharField(source="get_full_name")
    preferred_language = serializers.CharField()


class CurrentUserView(APIView):
    permission_classes = [HasDashboardAccess]

    @extend_schema(responses=CurrentUserSerializer, tags=["Authentication"])
    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)
