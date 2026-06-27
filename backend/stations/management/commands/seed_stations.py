from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from stations.models import Station, AirQualityReading
from django.utils import timezone
import datetime
import random

"""
Until ingestion with airflow is implemented, 
 just seeding with sample data
"""
IRISH_STATIONS = [
    {
        "openaq_id" : "EPA-69",
        "name" : "Pearse Street, Dublin 2",
        "city" : "Dublin",
        "lat" : 53.3451,
        "lon" : -6.2543,
    },
    {
        "openaq_id" : "EPA-56",
        "name" : "South Link Road, Cork",
        "city" : "Cork",
        "lat" : 51.8785,
        "lon" : -8.4649,
    },
    {
        "openaq_id" : "EPA-39",
        "name" : "People's Park, Limerick",
        "city" : "Limerick",
        "lat" : 52.6587,
        "lon" : -8.6287,
    },
    {
        "openaq_id": "EPA-87",
        "name": "Merchants Quay, Waterford",
        "city": "Waterford",
        "lat": 52.2638,
        "lon": -7.1180,
    },
    {
        "openaq_id": "EPA-25",
        "name": "Ennis, Co. Clare",
        "city": "Ennis",
        "lat": 52.8432,
        "lon": -8.9893,
    },
]

def calculate_aqi_from_pm25(pm25):
    if pm25 is None:
        return None

    breakpoints = [
        (0,   50,  0.0,   9.0),
        (51,  100, 9.1,   35.4),
        (101, 150, 35.5,  55.4),
        (151, 200, 55.5,  125.4),
        (201, 300, 125.5, 225.4),
        (301, 500, 225.5, 325.4),
    ]
    for aqi_lo, aqi_hi, c_lo, c_hi in breakpoints:
        if c_lo <= pm25 <= c_hi:
            aqi = ((aqi_hi - aqi_lo) / (c_hi - c_lo)) * (pm25 - c_lo) + aqi_lo
            return round(aqi)
    return 500


class Command(BaseCommand):
    help = 'Load EPA Ireland reference stations and optionally seed synthetic readings'
    def add_arguments(self, parser):
        parser.add_argument(
            '--with-readings',
            action='store_true',
            help='Generate 24 h of synthetic readings per station (dev only)',
        )
    def handle(self, *args, **options):
        created_count = 0
        for data in IRISH_STATIONS:
            station, created = Station.objects.get_or_create(
                openaq_id=data['openaq_id'],
                defaults={
                'name':data['name'],
                'city':data['city'],
                'location':Point(data['lon'], data['lat'], srid=4326),
                'is_active': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created: {station}')
            else:
                self.stdout.write(f'Already exists: {station}')

            if options['with_readings']:
                self._seed_readings(station)

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {created_count} new stations created '
                f'({len(IRISH_STATIONS) - created_count} already existed).'
            )
        )

    def _seed_readings(self, station):
        """Generate 24 synthetic hourly readings for local development.
        There are randomly generated at first, will be replaced by real OpenAQ data later.

        For now, synthetic data range was arbitrarily chosen based on info available on https://www.airquality.ie/
        """
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        readings_created = 0

        for hours_ago in range(24, 0, -1):
            ts = now - datetime.timedelta(hours=hours_ago)
            pm25 = round(random.uniform(2.0, 18.0), 1)

            _, created = AirQualityReading.objects.get_or_create(
                station=station,
                timestamp=ts,
                defaults={
                    'pm25': pm25,
                    'pm10': round(pm25 * random.uniform(1.3, 1.8), 1),
                    'no2': round(random.uniform(8.0, 35.0), 1),
                    'o3': round(random.uniform(30.0, 75.0), 1),
                    'co': round(random.uniform(0.1, 0.5), 2),
                    'aqi': calculate_aqi_from_pm25(pm25),
                },
            )
            if created:
                readings_created += 1

        self.stdout.write(
            f'    → {readings_created} synthetic readings added for {station.name}'
        )