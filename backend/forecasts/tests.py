from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from stations.models import Station
from .models import ForecastRun, ForecastPrediction


def _auth_mock():
    """Mock response for POST /auth/token (Airflow JWT)."""
    m = MagicMock()
    m.json.return_value = {'access_token': 'mock-airflow-token'}
    m.raise_for_status.return_value = None
    return m


def _dag_mock(dag_run_id='forecast_dag__2026-01-01T10:00:00'):
    """Mock response for POST /api/v2/dags/.../dagRuns."""
    m = MagicMock()
    m.json.return_value = {'dag_run_id': dag_run_id}
    m.raise_for_status.return_value = None
    return m


def _airflow_get_mock(state='success'):
    """Mock response for GET /api/v2/dags/.../dagRuns/..."""
    m = MagicMock()
    m.json.return_value = {'state': state}
    m.raise_for_status.return_value = None
    return m


NO_AIRFLOW = {'AIRFLOW_BASE_URL': ''}
NO_MLFLOW  = {'MLFLOW_TRACKING_URI': ''}
AIRFLOW_ENV = {
    'AIRFLOW_BASE_URL': 'http://mock-airflow:8080',
    'AIRFLOW_USER':     'admin',
    'AIRFLOW_PASSWORD': 'admin',
}


class JWTAuthTests(APITestCase):
    """Verify the JWT token flow works end to end."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )

    def test_obtain_token_with_valid_credentials(self):
        response = self.client.post('/api/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access',  response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_token_with_wrong_password(self):
        response = self.client.post('/api/token/', {
            'username': 'testuser',
            'password': 'wrongpassword',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_returns_new_access_token(self):
        resp = self.client.post('/api/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        }, format='json')
        refresh_token = resp.data['refresh']

        resp2 = self.client.post('/api/token/refresh/', {
            'refresh': refresh_token,
        }, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp2.data)

    def test_protected_endpoint_requires_token(self):
        response = self.client.post('/api/forecasts/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch.dict('os.environ', NO_AIRFLOW)
    def test_protected_endpoint_accessible_with_valid_token(self):
        station = Station.objects.create(
            openaq_id='TEST-AUTH',
            name='Test Station',
            city='Dublin',
            location=Point(-6.26, 53.35, srid=4326),
        )
        resp = self.client.post('/api/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        }, format='json')
        token = resp.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/forecasts/', {
            'station_id': station.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
        response = self.client.post('/api/forecasts/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ForecastRunTests(APITestCase):
    """Tests for forecast pipeline creation and status polling."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        self.station = Station.objects.create(
            openaq_id='TEST-FC01',
            name='Dublin City Centre',
            city='Dublin',
            location=Point(-6.2603, 53.3498, srid=4326),
        )
        resp = self.client.post('/api/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')

    # ── Create (no Airflow) ───────────────────────────────────────────────────

    @patch.dict('os.environ', NO_AIRFLOW)
    def test_create_forecast_returns_201(self):
        response = self.client.post('/api/forecasts/', {
            'station_id': self.station.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch.dict('os.environ', NO_AIRFLOW)
    def test_create_forecast_status_is_queued_without_airflow(self):
        """When AIRFLOW_BASE_URL is not set the run is created as queued."""
        response = self.client.post('/api/forecasts/', {
            'station_id': self.station.id,
        }, format='json')
        self.assertEqual(response.data['status'], 'queued')

    @patch.dict('os.environ', NO_AIRFLOW)
    def test_create_forecast_creates_db_record(self):
        self.client.post('/api/forecasts/', {
            'station_id': self.station.id,
        }, format='json')
        self.assertEqual(ForecastRun.objects.count(), 1)
        run = ForecastRun.objects.first()
        self.assertEqual(run.station, self.station)
        self.assertEqual(run.status, ForecastRun.STATUS_QUEUED)

    @patch.dict('os.environ', NO_AIRFLOW)
    def test_create_forecast_response_contains_station_name(self):
        response = self.client.post('/api/forecasts/', {
            'station_id': self.station.id,
        }, format='json')
        self.assertEqual(response.data['station_name'], 'Dublin City Centre')

    def test_create_forecast_invalid_station_returns_404(self):
        response = self.client.post('/api/forecasts/', {
            'station_id': 99999,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_forecast_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post('/api/forecasts/', {
            'station_id': self.station.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Create (with Airflow mocked) ──────────────────────────────────────────

    @patch('forecasts.views.http_client.post')
    def test_create_forecast_calls_airflow_when_configured(self, mock_post):
        """
        When AIRFLOW_BASE_URL is set, the view should call the Airflow REST
        API and store the returned dag_run_id on the ForecastRun record.
        _airflow_headers() makes a POST /auth/token call first, then the
        view makes a POST /dagRuns call — mock both in order.
        """
        mock_post.side_effect = [_auth_mock(), _dag_mock()]

        with patch.dict('os.environ', AIRFLOW_ENV):
            response = self.client.post('/api/forecasts/', {
                'station_id': self.station.id,
            }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['dag_run_id'],
            'forecast_dag__2026-01-01T10:00:00',
        )
        self.assertEqual(response.data['status'], 'running')

    @patch('forecasts.views.http_client.post')
    def test_airflow_failure_sets_status_to_failed(self, mock_post):
        mock_post.side_effect = ConnectionError("Airflow is down")

        with patch.dict('os.environ', AIRFLOW_ENV):
            response = self.client.post('/api/forecasts/', {
                'station_id': self.station.id,
            }, format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        run = ForecastRun.objects.first()
        self.assertEqual(run.status, ForecastRun.STATUS_FAILED)

    # ── Status ────────────────────────────────────────────────────────────────

    def test_get_status_returns_200(self):
        run = ForecastRun.objects.create(
            station=self.station, status=ForecastRun.STATUS_QUEUED
        )
        response = self.client.get(f'/api/forecasts/{run.id}/status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_status_returns_current_status(self):
        run = ForecastRun.objects.create(
            station=self.station, status=ForecastRun.STATUS_RUNNING,
            dag_run_id='test-run-id',
        )
        response = self.client.get(f'/api/forecasts/{run.id}/status/')
        self.assertEqual(response.data['status'], 'running')

    @patch('forecasts.views.http_client.post')
    @patch('forecasts.views.http_client.get')
    def test_status_syncs_from_airflow_when_configured(self, mock_get, mock_post):
        """When Airflow reports 'success', Django should update the run.
        pipeline_status calls _airflow_headers() (POST) then the DAG run
        endpoint (GET) — both must be mocked.
        """
        run = ForecastRun.objects.create(
            station=self.station,
            status=ForecastRun.STATUS_RUNNING,
            dag_run_id='test-run-id',
        )
        mock_post.return_value = _auth_mock()
        mock_get.return_value  = _airflow_get_mock(state='success')

        with patch.dict('os.environ', AIRFLOW_ENV):
            response = self.client.get(f'/api/forecasts/{run.id}/status/')

        self.assertEqual(response.data['status'], 'success')
        run.refresh_from_db()
        self.assertEqual(run.status, ForecastRun.STATUS_SUCCESS)

    def test_status_unauthenticated_returns_401(self):
        run = ForecastRun.objects.create(station=self.station)
        self.client.credentials()
        response = self.client.get(f'/api/forecasts/{run.id}/status/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Predictions ───────────────────────────────────────────────────────────

    def test_predictions_empty_for_new_run(self):
        run = ForecastRun.objects.create(station=self.station)
        response = self.client.get(f'/api/forecasts/{run.id}/predictions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_predictions_returns_all_for_completed_run(self):
        run = ForecastRun.objects.create(
            station=self.station, status=ForecastRun.STATUS_SUCCESS
        )
        now = timezone.now()
        for i in range(24):
            ForecastPrediction.objects.create(
                forecast_run=run,
                timestamp=now + timezone.timedelta(hours=i + 1),
                predicted_pm25=10.0 + i,
                confidence_lower=8.0 + i,
                confidence_upper=12.0 + i,
            )
        response = self.client.get(f'/api/forecasts/{run.id}/predictions/')
        self.assertEqual(len(response.data), 24)
        self.assertAlmostEqual(response.data[0]['predicted_pm25'], 10.0)
        self.assertAlmostEqual(response.data[23]['predicted_pm25'], 33.0)

    def test_predictions_contains_confidence_interval(self):
        run = ForecastRun.objects.create(station=self.station)
        ForecastPrediction.objects.create(
            forecast_run=run,
            timestamp=timezone.now() + timezone.timedelta(hours=1),
            predicted_pm25=15.0,
            confidence_lower=12.0,
            confidence_upper=18.0,
        )
        response = self.client.get(f'/api/forecasts/{run.id}/predictions/')
        pred = response.data[0]
        self.assertIn('confidence_lower', pred)
        self.assertIn('confidence_upper', pred)
        self.assertAlmostEqual(pred['confidence_lower'], 12.0)

    # ── MLflow models ─────────────────────────────────────────────────────────

    @patch.dict('os.environ', NO_MLFLOW)
    def test_mlflow_models_returns_empty_without_mlflow(self):
        """Without MLFLOW_TRACKING_URI set, returns empty list with message."""
        response = self.client.get('/api/mlflow-models/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['models'], [])
        self.assertIn('message', response.data)

    @patch.dict('os.environ', NO_MLFLOW)
    def test_mlflow_models_no_auth_required(self):
        """Model listing is public — no token needed."""
        self.client.credentials()
        response = self.client.get('/api/mlflow-models/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
