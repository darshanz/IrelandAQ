from rest_framework import serializers
from .models import ForecastRun, ForecastPrediction


class ForecastPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastPrediction
        fields = [
            'id', 'timestamp',
            'predicted_pm25',
            'confidence_lower',
            'confidence_upper',
        ]


class ForecastRunSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)

    class Meta:
        model = ForecastRun
        fields = [
            'id',
            'station', 'station_name',
            'dag_run_id',
            'mlflow_run_id', 'model_uri', 'ml_tracking_uri',
            'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id',
            'dag_run_id',
            'mlflow_run_id', 'model_uri', 'ml_tracking_uri',
            'status',
            'created_at', 'updated_at',
        ]