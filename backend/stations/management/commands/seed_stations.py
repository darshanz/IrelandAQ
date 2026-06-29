import os
import datetime
import random
import requests

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone

from stations.models import Station, AirQualityReading

OPENAQ_BASE  = "https://api.openaq.org/v3"
IRELAND_BBOX = "-10.5,51.4,-5.5,55.4"
STALE_DAYS   = 90  # skip stations with no data in the last 90 days

# just in case,
# if OpenAQ api fails, we still can populate the seed locations.
# these were from openaq api (active stations on June 28, 2026)
FALLBACK_STATIONS = [
    {"openaq_id": "4858",    "name": "Dublin Winetavern Street",          "city": "Dublin",    "lat": 53.3417, "lon": -6.2889},
    {"openaq_id": "2162824", "name": "Cork UCC Distillery Fields",         "city": "Cork",      "lat": 51.9001, "lon": -8.4864},
    {"openaq_id": "2162821", "name": "Waterford City Paddy Brownes Road",  "city": "Waterford", "lat": 52.2471, "lon": -7.1516},
    {"openaq_id": "2162811", "name": "Louth Dundalk Meadow Grove",         "city": "Dundalk",   "lat": 54.0031, "lon": -6.3926},
    {"openaq_id": "6406",    "name": "Wexford Enniscorthy Parnell Road",   "city": "Wexford",   "lat": 52.4985, "lon": -6.5707},
]


def _extract_city(name: str, locality: str | None) -> str:
    """ getting city name from OpenAQ location data.
    The locality field is often a long network description string rather than
    a city name. Fall back to the first word of the station name, which for
    Irish EPA stations is always the county or city (e.g. 'Dublin', 'Cork').
    """
    if (locality
            and len(locality) < 60
            and "e-Reporting" not in locality
            and "network" not in locality.lower()):
        return locality
    return name.split()[0] if name else "Ireland"


def _discover_stations(api_key: str) -> list[dict]:
    """
    Query OpenAQ v3 for all active Irish stations that have a pm25 sensor.

    Uses a bounding box covering the island of Ireland rather than
    country=IE, which does not filter reliably in the v3 API.
    Paginates until all results are fetched and filters out stations
    whose last reading is older than STALE_DAYS.
    """
    cutoff = timezone.now() - datetime.timedelta(days=STALE_DAYS)
    stations = []
    page = 1

    while True:
        resp = requests.get(
            f"{OPENAQ_BASE}/locations",
            headers={"X-API-Key": api_key},
            params={"bbox": IRELAND_BBOX, "limit": 100, "page": page},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            break

        for loc in results:
            # Must have a pm25 sensor
            has_pm25 = any(
                s.get("parameter", {}).get("name") == "pm25"
                for s in loc.get("sensors", [])
            )
            if not has_pm25:
                continue

            # Must have recent data
            dt_str = loc.get("datetimeLast", {}).get("utc", "")
            if not dt_str:
                continue
            try:
                last = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if last < cutoff:
                    continue
            except ValueError:
                continue

            coords = loc.get("coordinates", {})
            lat, lon = coords.get("latitude"), coords.get("longitude")
            if lat is None or lon is None:
                continue

            stations.append({
                "openaq_id": str(loc["id"]),
                "name": loc.get("name", f"Station {loc['id']}"),
                "city": _extract_city(loc.get("name", ""), loc.get("locality")),
                "lat": lat,
                "lon": lon,
            })

        if len(results) < 100:
            break
        page += 1

    return stations


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
    help = 'Discover active Irish stations from OpenAQ and seed synthetic readings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-readings',
            action='store_true',
            help='Generate 24h of synthetic readings per station (dev only)',
        )

    def handle(self, *args, **options):
        api_key = os.environ.get("OPENAQ_API_KEY", "")

        if api_key:
            self.stdout.write("Discovering stations from OpenAQ API...")
            try:
                stations = _discover_stations(api_key)
                self.stdout.write(
                    f"  Found {len(stations)} active Irish stations with pm25 data."
                )
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f"  OpenAQ discovery failed ({exc}), using fallback list."
                ))
                stations = FALLBACK_STATIONS
        else:
            self.stdout.write(self.style.WARNING(
                "OPENAQ_API_KEY not set — using fallback station list."
            ))
            stations = FALLBACK_STATIONS

        created_count = 0
        for data in stations:
            station, created = Station.objects.get_or_create(
                openaq_id=data["openaq_id"],
                defaults={
                    "name":      data["name"],
                    "city":      data["city"],
                    "location":  Point(data["lon"], data["lat"], srid=4326),
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created: {station}")
            else:
                self.stdout.write(f"  Already exists: {station}")

            if options["with_readings"]:
                self._seed_readings(station)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created_count} new stations created "
            f"({len(stations) - created_count} already existed)."
        ))

    def _seed_readings(self, station):
        """Generate 24 synthetic hourly readings for local development.

        Values are randomised within ranges typical for Irish urban monitoring
        sites (EPA Ireland annual reports 2022-2024). These are replaced by
        real OpenAQ data once the Airflow ingestion DAG runs.
        """
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        readings_created = 0

        for hours_ago in range(24, 0, -1):
            ts   = now - datetime.timedelta(hours=hours_ago)
            pm25 = round(random.uniform(2.0, 18.0), 1)

            _, created = AirQualityReading.objects.get_or_create(
                station=station,
                timestamp=ts,
                defaults={
                    "pm25": pm25,
                    "pm10": round(pm25 * random.uniform(1.3, 1.8), 1),
                    "no2":  round(random.uniform(8.0, 35.0), 1),
                    "o3":   round(random.uniform(30.0, 75.0), 1),
                    "co":   round(random.uniform(0.1, 0.5), 2),
                    "aqi":  calculate_aqi_from_pm25(pm25),
                },
            )
            if created:
                readings_created += 1

        self.stdout.write(
            f"    → {readings_created} synthetic readings added for {station.name}"
        )
