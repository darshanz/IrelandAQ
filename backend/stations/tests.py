from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Station, AirQualityReading

class StationAPITests(APITestCase):
    """Tests for the stations API endpoints."""

    def setUp(self):
        self.dublin = Station.objects.create(
            openaq_id='TEST-D01',
            name='Dublin City Centre',
            city='Dublin',
            location=Point(-6.2603, 53.3498, srid=4326),
        )
        self.cork = Station.objects.create(
            openaq_id='TEST-C01',
            name='Cork Civic Offices',
            city='Cork',
            location=Point(-8.4756, 51.8985, srid=4326),
        )

    def test_list_stations_returns_200(self):
        response = self.client.get('/api/stations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_stations_returns_all_active(self):
        response = self.client.get('/api/stations/')
        self.assertEqual(len(response.data), 2)

    def test_inactive_station_excluded_from_list(self):
        self.dublin.is_active = False
        self.dublin.save()
        response = self.client.get('/api/stations/')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Cork Civic Offices')

    def test_station_response_has_expected_fields(self):
        response = self.client.get('/api/stations/')
        station = response.data[0]
        for field in ['id', 'name', 'city', 'latitude', 'longitude', 'is_active']:
            self.assertIn(field, station, msg=f"Field '{field}' missing from response")

    def test_station_detail_returns_200(self):
        response = self.client.get(f'/api/stations/{self.dublin.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Dublin City Centre')

    def test_station_detail_has_correct_coordinates(self):
        response = self.client.get(f'/api/stations/{self.dublin.id}/')
        self.assertAlmostEqual(response.data['latitude'],  53.3498, places=3)
        self.assertAlmostEqual(response.data['longitude'], -6.2603, places=3)

    def test_nearby_finds_dublin_from_city_centre(self):
        """A 10 km radius from Dublin city centre should include our Dublin station."""
        response = self.client.get(
            '/api/stations/nearby/?lat=53.3498&lon=-6.2603&radius=10'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Dublin City Centre')

    def test_nearby_excludes_station_beyond_radius(self):
        """A 10 km radius from Dublin should NOT include Cork (258 km away)."""
        response = self.client.get(
            '/api/stations/nearby/?lat=53.3498&lon=-6.2603&radius=10'
        )
        names = [s['name'] for s in response.data]
        self.assertNotIn('Cork Civic Offices', names)

    def test_nearby_finds_both_with_large_radius(self):
        """A 400 km radius from Limerick should include both Dublin and Cork."""
        response = self.client.get(
            '/api/stations/nearby/?lat=52.668&lon=-8.630&radius=400'
        )
        self.assertEqual(len(response.data), 2)

    def test_nearby_from_london_finds_nothing(self):
        """London is outside Ireland — no stations should be found nearby."""
        response = self.client.get(
            '/api/stations/nearby/?lat=51.5&lon=-0.1&radius=50'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_nearby_invalid_params_returns_400(self):
        response = self.client.get(
            '/api/stations/nearby/?lat=not-a-number&lon=-6.2&radius=50'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_readings_returns_200_with_no_data(self):
        response = self.client.get(f'/api/stations/{self.dublin.id}/readings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_readings_returns_last_24_hours(self):
        # Create a reading from 12 hours ago — should appear
        AirQualityReading.objects.create(
            station=self.dublin,
            timestamp=timezone.now() - timezone.timedelta(hours=12),
            pm25=15.0, aqi=60,
        )
        # Create a reading from 48 hours ago — should NOT appear
        AirQualityReading.objects.create(
            station=self.dublin,
            timestamp=timezone.now() - timezone.timedelta(hours=48),
            pm25=20.0, aqi=70,
        )
        response = self.client.get(f'/api/stations/{self.dublin.id}/readings/')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['pm25'], 15.0)

    # Current AQI

    def test_current_aqi_returns_none_when_no_readings(self):
        response = self.client.get(f'/api/stations/{self.dublin.id}/current-aqi/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['aqi'])

    def test_current_aqi_returns_latest_reading(self):
        AirQualityReading.objects.create(
            station=self.dublin,
            timestamp=timezone.now() - timezone.timedelta(hours=2),
            pm25=10.0, aqi=42,
        )
        AirQualityReading.objects.create(
            station=self.dublin,
            timestamp=timezone.now() - timezone.timedelta(hours=1),
            pm25=20.0, aqi=68,   # ← this is more recent
        )
        response = self.client.get(f'/api/stations/{self.dublin.id}/current-aqi/')
        self.assertEqual(response.data['aqi'], 68)

    def test_health_check(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
