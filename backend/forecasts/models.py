from django.db import models


class ForecastRun(models.Model):
    """
    Records one forecast pipeline execution.
    Django stores the Airflow dag_run_id so it can poll Airflow for status updates, and the MLflow identifiers
    so the frontend can link to the experiment that produced the model.
    """
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    station = models.ForeignKey(
        'stations.Station',
        on_delete=models.CASCADE,
        related_name='forecasts',
    )

    # dag_run_id will be empty string until Airflow responds.
    dag_run_id = models.CharField(max_length=200, blank=True)

    # MLflow identifiers
    mlflow_run_id= models.CharField(max_length=200, blank=True)
    model_uri= models.CharField(max_length=500, blank=True)
    ml_tracking_uri = models.CharField(max_length=500, blank=True)

    status= models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Forecast for {self.station.name} [{self.status}]"


class ForecastPrediction(models.Model):
    """
    Hourly PM2.5 prediction produced by a completed ForecastRun.
    """
    forecast_run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name='predictions',
    )
    timestamp = models.DateTimeField()
    predicted_pm25 = models.FloatField()

    # for 90% confidence interval. (optional as may not be available for all models)
    confidence_lower = models.FloatField(null=True, blank=True)
    confidence_upper = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.forecast_run} @ {self.timestamp:%Y-%m-%d %H:%M}"