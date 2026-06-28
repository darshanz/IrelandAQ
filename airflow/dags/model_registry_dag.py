import logging

import mlflow
import pendulum
from airflow.sdk import dag, task

log = logging.getLogger(__name__)

MODEL_NAME = "irelandaq-pm25-forecast"


@dag(
    dag_id="model_registry_dag",
    description="Promote the best recent model to the MLflow Production stage.",
    schedule="@weekly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["mlflow", "governance"],
)
def model_registry_dag():

    @task
    def find_best_model() -> dict | None:
        import os
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(tracking_uri)
        client = mlflow.MlflowClient()

        try:
            runs = mlflow.search_runs(
                experiment_names=[
                    e.name for e in client.search_experiments()
                    if e.name.startswith("irelandaq-station-")
                ],
                filter_string="metrics.train_rmse < 50",
                order_by=["metrics.train_rmse ASC"],
                max_results=1,
            )
        except Exception as exc:
            log.warning("MLflow search failed: %s", exc)
            return None

        if runs.empty:
            log.info("No qualifying runs found. Skipping promotion.")
            return None

        best_run_id = runs.iloc[0]["run_id"]
        best_rmse = runs.iloc[0]["metrics.train_rmse"]
        log.info("Best run: %s (RMSE=%.3f)", best_run_id, best_rmse)
        return {"run_id": best_run_id, "rmse": best_rmse}

    @task
    def promote_to_production(best: dict | None) -> None:
        import os
        if best is None:
            log.info("Nothing to promote.")
            return

        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(tracking_uri)
        client = mlflow.MlflowClient()

        model_uri = f"runs:/{best['run_id']}/model"
        mv = mlflow.register_model(model_uri, MODEL_NAME)
        log.info("Registered model version %s", mv.version)

        # Archive any current Production versions
        try:
            for v in client.get_latest_versions(MODEL_NAME, stages=["Production"]):
                if v.version != mv.version:
                    client.transition_model_version_stage(
                        name=MODEL_NAME, version=v.version, stage="Archived"
                    )
                    log.info("Archived previous Production version %s.", v.version)
        except Exception as exc:
            log.warning("Error archiving old version: %s", exc)

        # Promote the new version
        client.transition_model_version_stage(
            name=MODEL_NAME, version=mv.version, stage="Production"
        )
        log.info(
            "Promoted version %s to Production (RMSE=%.3f).",
            mv.version,
            best["rmse"],
        )

    best = find_best_model()
    promote_to_production(best)


model_registry_dag()