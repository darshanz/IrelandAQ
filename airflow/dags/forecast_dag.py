import os
import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import pendulum
import psycopg2.extras
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from airflow.sdk import dag, task

from db_utils import get_conn, update_forecast_run

log = logging.getLogger(__name__)

MIN_READINGS = 36    # minimum hours of history required to train
FORECAST_HOURS = 24    # hours to predict ahead
HISTORY_HOURS = 72    # hours of history to use as training window


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("timestamp").copy()
    df["hour"] = df["timestamp"].dt.hour
    df["dow"] = df["timestamp"].dt.dayofweek

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)

    df["lag_1h"] = df["pm25"].shift(1)
    df["lag_2h"] = df["pm25"].shift(2)
    df["lag_3h"] = df["pm25"].shift(3)
    df["lag_24h"] = df["pm25"].shift(24)

    df["roll_3h"] = df["pm25"].rolling(3,  min_periods=1).mean()
    df["roll_6h"] = df["pm25"].rolling(6,  min_periods=1).mean()

    return df.dropna()


FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "lag_1h", "lag_2h", "lag_3h", "lag_24h",
    "roll_3h", "roll_6h",
]



@dag(
    dag_id="forecast_dag",
    description="Train a forecast model and write 24-hour predictions.",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["forecast", "ml"],
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=5)},
)
def forecast_dag():

    @task
    def prepare_run(**context) -> dict:
        """
        Read station_id and run_db_id from the trigger conf.
        Mark the ForecastRun as 'running'.
        Load the last HISTORY_HOURS of PM2.5 readings for the station.
        Return the readings and run metadata for downstream tasks.
        """
        conf = context["dag_run"].conf or {}
        station_id = conf.get("station_id")
        run_db_id = conf.get("run_db_id")

        if not station_id or not run_db_id:
            raise ValueError(
                "forecast_dag requires conf={'station_id': N, 'run_db_id': N}. "
                "Trigger this DAG via POST /api/forecasts/, not directly."
            )

        update_forecast_run(run_db_id, status="running")
        log.info("ForecastRun %d → running", run_db_id)

        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT timestamp, pm25
                    FROM   stations_airqualityreading
                    WHERE  station_id = %s
                      AND  timestamp  >= NOW() - INTERVAL '%s hours'
                    ORDER  BY timestamp
                    """,
                    (station_id, HISTORY_HOURS),
                )
                rows = [dict(r) for r in cur.fetchall()]

        log.info("Loaded %d readings for station %d.", len(rows), station_id)

        if len(rows) < MIN_READINGS:
            update_forecast_run(run_db_id, status="failed")
            raise ValueError(
                f"Station {station_id} has only {len(rows)} readings, "
                f"minimum {MIN_READINGS} required for training. "
                f"Run data_ingestion_dag first, or wait for more readings to accumulate."
            )

        return {
            "station_id": station_id,
            "run_db_id":  run_db_id,
            "readings":   [
                {"timestamp": r["timestamp"].isoformat(), "pm25": r["pm25"]}
                for r in rows
            ],
        }

    @task
    def train_model(run_meta: dict) -> dict:
        df = pd.DataFrame(run_meta["readings"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = build_features(df)

        X = df[FEATURE_COLS].values
        y = df["pm25"].values

        model = LinearRegression()
        model.fit(X, y)

        y_pred = model.predict(X)
        residuals = y - y_pred
        mae = mean_absolute_error(y, y_pred)
        rmse = mean_squared_error(y, y_pred) ** 0.5
        residual_std = max(float(np.std(residuals)), 1.5)  # floor so confidence band is visible

        log.info("Train MAE=%.3f, RMSE=%.3f, ResidualStd=%.3f", mae, rmse, residual_std)

        # Build 24-hour forecast iteratively with exponential smoothing.
        # Each raw prediction is smoothed against the previous step before being
        # fed back as the next lag — this breaks the amplification loop that
        # causes linear models to oscillate when iterated over long horizons.
        ALPHA = 0.4   # smoothing weight on raw prediction (1-alpha on prev smoothed)
        history_pm25 = df["pm25"].tolist()
        predictions = []
        last_ts = df["timestamp"].iloc[-1]

        for h in range(1, FORECAST_HOURS + 1):
            future_ts = last_ts + pd.Timedelta(hours=h)
            row = {
                "hour_sin": np.sin(2 * np.pi * future_ts.hour / 24),
                "hour_cos": np.cos(2 * np.pi * future_ts.hour / 24),
                "dow_sin":  np.sin(2 * np.pi * future_ts.dayofweek / 7),
                "dow_cos":  np.cos(2 * np.pi * future_ts.dayofweek / 7),
                "lag_1h":  history_pm25[-1],
                "lag_2h":  history_pm25[-2] if len(history_pm25) >= 2 else history_pm25[-1],
                "lag_3h":  history_pm25[-3] if len(history_pm25) >= 3 else history_pm25[-1],
                "lag_24h": history_pm25[-24] if len(history_pm25) >= 24 else history_pm25[0],
                "roll_3h": float(np.mean(history_pm25[-3:])),
                "roll_6h": float(np.mean(history_pm25[-6:])),
            }
            x_vec = np.array([[row[c] for c in FEATURE_COLS]])
            raw_hat = max(0.0, float(model.predict(x_vec)[0]))
            # Smooth before appending so the next step sees a dampened value
            pm25_hat = ALPHA * raw_hat + (1 - ALPHA) * history_pm25[-1]
            history_pm25.append(pm25_hat)

            predictions.append({
                "timestamp": future_ts.isoformat(),
                "predicted_pm25": pm25_hat,
                "confidence_lower": max(0.0, pm25_hat - residual_std),
                "confidence_upper": pm25_hat + residual_std,
            })

        return {
            "station_id": run_meta["station_id"],
            "run_db_id": run_meta["run_db_id"],
            "readings": run_meta["readings"],   # passed to log_to_mlflow
            "predictions": predictions,
            "metrics": {
                "train_mae": mae,
                "train_rmse": rmse,
                "residual_std": residual_std,
                "n_train_samples": len(df),
            },
            "params": {
                "model_type": "LinearRegression",
                "feature_cols": ",".join(FEATURE_COLS),
                "history_hours": HISTORY_HOURS,
                "forecast_hours": FORECAST_HOURS,
                "min_readings": MIN_READINGS,
            },
        }

    @task
    def write_predictions(model_output: dict) -> dict:
        run_db_id = model_output["run_db_id"]
        predictions = model_output["predictions"]

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM forecasts_forecastprediction WHERE forecast_run_id = %s",
                    (run_db_id,),
                )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO forecasts_forecastprediction
                        (forecast_run_id, timestamp, predicted_pm25, confidence_lower, confidence_upper)
                    VALUES %s
                    """,
                    [
                        (
                            run_db_id,
                            p["timestamp"],
                            p["predicted_pm25"],
                            p["confidence_lower"],
                            p["confidence_upper"],
                        )
                        for p in predictions
                    ],
                )
        log.info("Wrote %d predictions for ForecastRun %d.", len(predictions), run_db_id)
        return model_output

    @task
    def log_to_mlflow(model_output: dict) -> None:
        run_db_id = model_output["run_db_id"]
        station_id = model_output["station_id"]

        df = pd.DataFrame(model_output["readings"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = build_features(df)

        X = df[FEATURE_COLS].values
        y = df["pm25"].values
        model = LinearRegression()
        model.fit(X, y)

        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(f"irelandaq-station-{station_id}")

        with mlflow.start_run(run_name=f"forecast-run-{run_db_id}") as run:
            mlflow.log_params(model_output["params"])
            mlflow.log_metrics(model_output["metrics"])
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="model",
                registered_model_name="irelandaq-pm25-forecast",
            )
            mlflow_run_id = run.info.run_id

        model_uri = f"runs:/{mlflow_run_id}/model"
        log.info("MLflow run_id=%s, model_uri=%s", mlflow_run_id, model_uri)

        update_forecast_run(
            run_db_id,
            status = "success",
            mlflow_run_id = mlflow_run_id,
            model_uri = model_uri,
            ml_tracking_uri = tracking_uri,
        )
        log.info("ForecastRun %d → success", run_db_id)

    run_meta = prepare_run()
    model_output = train_model(run_meta)
    model_output = write_predictions(model_output)
    log_to_mlflow(model_output)


forecast_dag()