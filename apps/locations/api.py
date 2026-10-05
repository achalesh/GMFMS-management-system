from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from .models import Block, District, GramaPanchayat
from .selectors import active_blocks, active_districts, active_panchayats


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ["id", "district_code", "name_en", "name_ml"]


class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Block
        fields = ["id", "district", "block_code", "name_en", "name_ml"]


class PanchayatSerializer(serializers.ModelSerializer):
    district = serializers.IntegerField(source="block.district_id", read_only=True)

    class Meta:
        model = GramaPanchayat
        fields = ["id", "district", "block", "sec_local_body_code", "name_en", "name_ml"]


class LocationPagination(generics.ListAPIView.pagination_class):
    page_size = 100
    max_page_size = 100


class PublicLocationList(generics.ListAPIView):
    # Explicit exception to the authenticated API default: only active location
    # labels/codes are public. No contacts or application data are serialized.
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    pagination_class = LocationPagination


class DistrictList(PublicLocationList):
    serializer_class = DistrictSerializer

    def get_queryset(self):
        return active_districts()


def parent_parameter(request, key):
    value = request.query_params.get(key)
    if (
        not value
        or not value.isascii()
        or not value.isdigit()
        or len(value) > 10
        or int(value) <= 0
    ):
        raise ValidationError({key: f"A positive {key} ID is required."})
    return int(value)


@extend_schema(parameters=[OpenApiParameter("district", int, required=True)])
class BlockList(PublicLocationList):
    queryset = Block.objects.none()
    serializer_class = BlockSerializer

    def get_queryset(self):
        return active_blocks().filter(district_id=parent_parameter(self.request, "district"))


@extend_schema(parameters=[OpenApiParameter("block", int, required=True)])
class PanchayatList(PublicLocationList):
    queryset = GramaPanchayat.objects.none()
    serializer_class = PanchayatSerializer

    def get_queryset(self):
        return (
            active_panchayats()
            .filter(block_id=parent_parameter(self.request, "block"))
            .select_related("block")
        )
