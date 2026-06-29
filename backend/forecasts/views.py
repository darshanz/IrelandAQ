import os

import requests as http_client
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from stations.models import Station
from .models import ForecastRun, ForecastPrediction
from .serializers import ForecastRunSerializer, ForecastPredictionSerializer


def _airflow_headers() -> dict:
    """
    Airflow 3.x uses bearer token auth for the REST API.
    Exchange username/password for a short-lived JWT via POST /auth/token.
    """
    airflow_url = os.environ.get('AIRFLOW_BASE_URL', '')
    resp = http_client.post(
        f"{airflow_url}/auth/token",
        json={
            "username": os.environ.get('AIRFLOW_USER', 'admin'),
            "password": os.environ.get('AIRFLOW_PASSWORD', ''),
        },
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class ForecastViewSet(viewsets.GenericViewSet):
    """
    Handles forecast pipeline operations.
    """
    serializer_class = ForecastRunSerializer
    permission_classes = [IsAuthenticated]
    queryset = ForecastRun.objects.all()

    # POST /api/forecasts/ — trigger a new forecast

    def create(self, request):
        """
        Trigger a forecast pipeline for a station.
        """
        station_id = request.data.get('station_id')
        # if station exists
        station = get_object_or_404(Station, id=station_id, is_active=True)

        # create a forecast run record as queued
        run = ForecastRun.objects.create(
            station=station,
            status=ForecastRun.STATUS_QUEUED,
        )

        # fire airflow dag
        airflow_url = os.environ.get('AIRFLOW_BASE_URL')
        if not airflow_url:
            # if airflow not configured..
            serializer = self.get_serializer(run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # airflow is configured
        try:
            resp = http_client.post(
                f"{airflow_url}/api/v2/dags/forecast_dag/dagRuns",
                json={"logical_date": None, "conf": {"station_id": station.id, "run_db_id": run.id}},
                headers=_airflow_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            dag_data = resp.json()

            run.dag_run_id = dag_data.get('dag_run_id', '')
            run.status= ForecastRun.STATUS_RUNNING
            run.save()

        except Exception as exc:
            run.status = ForecastRun.STATUS_FAILED
            run.save()
            return Response(
                {'error': f'Airflow trigger failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = self.get_serializer(run)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    # GET /api/forecasts/{id}/
    def retrieve(self, request, pk=None):
        return self.pipeline_status(request, pk=pk)

    # GET /api/forecasts/{id}/status/
    @action(detail=True, methods=['get'], url_path='status')
    def pipeline_status(self, request, pk=None):
        """
        Poll airflow for the current DAG run state
        """
        run = get_object_or_404(ForecastRun, pk=pk)
        airflow_url = os.environ.get('AIRFLOW_BASE_URL')

        if run.dag_run_id and airflow_url:
            try:
                resp = http_client.get(
                    f"{airflow_url}/api/v2/dags/forecast_dag/dagRuns/{run.dag_run_id}",
                    headers=_airflow_headers(),
                    timeout=10,
                )
                resp.raise_for_status()
                airflow_state = resp.json().get('state', '')

                state_map = {
                    'success': ForecastRun.STATUS_SUCCESS,
                    'failed':  ForecastRun.STATUS_FAILED,
                    'running': ForecastRun.STATUS_RUNNING,
                    'queued':  ForecastRun.STATUS_QUEUED,
                }
                new_status = state_map.get(airflow_state)
                if new_status and new_status != run.status:
                    run.status = new_status
                    run.save()

            except Exception:
                pass  # Return last known status
        serializer = self.get_serializer(run)
        return Response(serializer.data)

    # GET /api/forecasts/{id}/predictions/
    @action(detail=True, methods=['get'], url_path='predictions')
    def predictions(self, request, pk=None):
        """
        Return predictions.
        """
        run = get_object_or_404(ForecastRun, pk=pk)
        predictions = run.predictions.all()
        serializer = ForecastPredictionSerializer(predictions, many=True)
        return Response(serializer.data)


class MLflowModelsView(APIView):
    """
    GET /api/mlflow-models/
    Lists available models in MLflow Model Registry.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        tracking_uri = os.environ.get('MLFLOW_TRACKING_URI')

        if not tracking_uri:
            return Response({
                'models':  [],
                'message': 'MLflow not configured.',
            })

        try:
            resp = http_client.get(
                f"{tracking_uri}/api/2.0/mlflow/registered-models/list",
                timeout=5,
            )
            resp.raise_for_status()
            raw_models = resp.json().get('registered_models', [])

            models = [
                {
                    'name': m.get('name'),
                    'latest_versions': [
                        {
                            'version': v.get('version'),
                            'stage': v.get('current_stage'),
                        }
                        for v in m.get('latest_versions', [])
                    ],
                }
                for m in raw_models
            ]
            return Response({'models': models})

        except Exception as exc:
            return Response(
                {'models': [], 'error': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )