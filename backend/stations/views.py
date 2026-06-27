from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import datetime
from .models import Station, AirQualityReading
from .serializers import (
    StationSerializer,
    StationDetailSerializer,
    AirQualityReadingSerializer,
    )


class StationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Station.objects.filter(is_active=True)
    serializer_class = StationSerializer
    permission_classes = [AllowAny]

    def get_seriallizer_class(self):
        if self.action == 'retrieve':
            return StationSerializer

    @action(detail=False, methods=['get'], url_path='nearby')
    def nearby(self, request):
        """
        GET /api/stations/nearby/?lat=53.3&lon=-6.2&radius=50
         all active stations within `radius` kilometres of the given coordinate.
         Uses PostGIS ST_DWithin under the hood.
        """
        try:
            lat = float(request.query_params.get('lat', 53.3498))
            lon = float(request.query_params.get('lon', -62603))
            radius_km = float(request.query_params.get('radius', 50))

        except (TypeError, ValueError):
            return Response({"error": "lat, lon, and radius must be numbers"}, status=400,)

        center = Point(lon, lat, srid=4326)

        stations = Station.objects.filter(
            is_active = True,
            location__dwithin = (center, Distance(km=radius_km))
        )

        serializer = self.get_serialiser(stations, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['get'], url_path='readings')
    def readings(self, request, pk=None):
        """
        GET /api/stations/{id}/readings/
         last 24 hours of air quality readings for a station.
        """
        station = self.get_object()
        since = timezone.now() - datetime.timedelta(hours=24)
        readings = station.readings.filter(timestamp__gte=since)
        serializer = AirQualityReadingSerializer(readings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='current-aqi')
    def current_aqi(self, request, pk=None):
        """
        GET /api/stations/{id}/current-aqi/
         the latest AQI value for a station
        """

        station = self.get_object()
        latest = station.readings.order_by('-timestamp').first()
        if latest is None:
            return Response({'aqi': None, 'message': 'No readings yet.'})
        return Response({
            'station_id':
                station.id,
            'station_name': station.name,
            'aqi': latest.aqi,
            'pm25': latest.pm25,
            'timestamp': latest.timestamp,
        })