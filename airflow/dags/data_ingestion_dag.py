import os
import logging
from datetime import datetime, timezone

import pendulum
import requests
import psycopg2.extras
from airflow.sdk import dag, task

from db_utils import get_conn

log = logging.getLogger(__name__)

OPENAQ_BASE    = "https://api.openaq.org/v3"
OPENAQ_HEADERS = {"X-API-Key": os.environ.get("OPENAQ_API_KEY", "")}


def fetch_latest_pm25(openaq_id: str) -> dict | None:
    """
    OpenAQ v3 /latest returns raw sensor readings without parameter names.
    We first resolve which sensorsId corresponds to pm25 from the location
    detail, then match it in the /latest response.
    """
    try:
        # Step 1: find the pm25 sensor ID for this location
        loc_resp = requests.get(
            f"{OPENAQ_BASE}/locations/{openaq_id}",
            headers=OPENAQ_HEADERS,
            timeout=15,
        )
        if loc_resp.status_code == 404:
            log.warning("OpenAQ location %s not found, skipping.", openaq_id)
            return None
        loc_resp.raise_for_status()

        sensors = loc_resp.json().get("results", [{}])[0].get("sensors", [])
        pm25_sensor_ids = {
            s["id"] for s in sensors
            if s.get("parameter", {}).get("name") == "pm25"
        }
        if not pm25_sensor_ids:
            log.warning("No pm25 sensor found for location %s", openaq_id)
            return None

        # Step 2: get latest readings and find the pm25 one
        resp = requests.get(
            f"{OPENAQ_BASE}/locations/{openaq_id}/latest",
            headers=OPENAQ_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as exc:
        log.warning("OpenAQ request failed for %s: %s", openaq_id, exc)
        return None

    for reading in results:
        if reading.get("sensorsId") in pm25_sensor_ids:
            return {
                "value": reading["value"],
                "last_updated": reading["datetime"]["utc"],
            }
    return None


@dag(
    dag_id="data_ingestion_dag",
    description="Hourly ingestion from OpenAQ for all active stations.",
    schedule="@hourly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["ingestion"],
    default_args={"retries": 2, "retry_delay": pendulum.duration(minutes=2)},
)
def data_ingestion_dag():
    @task
    def get_active_stations() -> list[dict]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, openaq_id FROM stations_station WHERE is_active = TRUE"
                )
                return [dict(row) for row in cur.fetchall()]

    @task
    def ingest_station_readings(stations: list[dict]) -> dict:
        inserted = 0
        skipped  = 0

        with get_conn() as conn:
            with conn.cursor() as cur:
                for station in stations:
                    reading = fetch_latest_pm25(station["openaq_id"])
                    if reading is None:
                        skipped += 1
                        continue

                    cur.execute(
                        """
                        INSERT INTO stations_airqualityreading
                        (station_id, timestamp, pm25, aqi)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (station_id, timestamp) DO NOTHING
                        """,
                        (
                            station["id"],
                            reading["last_updated"],
                            reading["value"],
                            _pm25_to_aqi(reading["value"]),
                        ),
                    )
                    if cur.rowcount > 0:
                        inserted += 1
                        log.info(
                            "Inserted reading for %s: PM2.5=%.1f",
                            station["name"],
                            reading["value"],
                        )
                    else:
                        log.debug("Reading already exists for %s, skipped.", station["name"])
                        skipped += 1

        log.info("Ingestion complete. Inserted: %d, Skipped: %d", inserted, skipped)
        return {"inserted": inserted, "skipped": skipped}

    stations = get_active_stations()
    ingest_station_readings(stations)


def _pm25_to_aqi(pm25: float) -> int:
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


data_ingestion_dag()
