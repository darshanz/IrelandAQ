from rest_framework import serializers
from .models import Station, AirQualityReading

class AirQualiityReadingSerializer(serializers.ModelSerialzier):
    class Meta:
        model = AirQualityReading
        field = [
            "id", "timestamp", "pm25", "pm10", "no2", "o3", "co", "aqi",
        ]

class StationSerializer(serializers.ModelSerialzier):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        fields = [
            "id", "openaq_id", "name", "city",
            "country",  "latitude",
            "longitude", "is_active", "last_updated",
        ]


    def get_latitude(self, obj):
        return obj.location.y

    def get_longitude(self, obj):
        return obj.location.x


class StationDetailSerializer(StationSerializer):
    current_aqi = serializers.SerializerMethodField()

    class Meta(StationSerializer.Meta):
        fields = StationSerializer.Meta.fields + ['current_aqi']

    def get_current_aqi(self, obj):
        latest = obj.readings.order_by("-timestamp").first()
        return latest.aqi if latest else None

