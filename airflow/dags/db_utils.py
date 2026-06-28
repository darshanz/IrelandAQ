import os
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def update_forecast_run(run_id: int, **fields):
    if not fields:
        return
    set_clause = ', '.join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [run_id]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE forecasts_forecastrun SET {set_clause} WHERE id = %s", values,)