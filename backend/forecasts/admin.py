from django.contrib import admin
from .models import ForecastRun, ForecastPrediction


class ForecastPredictionInline(admin.TabularInline):
    model = ForecastPrediction
    extra = 0
    readonly_fields = ['timestamp', 'predicted_pm25', 'confidence_lower', 'confidence_upper']
    can_delete= False


@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = ['id', 'station', 'status', 'dag_run_id', 'created_at']
    list_filter = ['status', 'station__city']
    search_fields = ['station__name', 'dag_run_id', 'mlflow_run_id']
    ordering = ['-created_at']
    readonly_fields = [
        'dag_run_id', 'mlflow_run_id', 'model_uri',
        'ml_tracking_uri', 'created_at', 'updated_at',
    ]
    inlines = [ForecastPredictionInline]


@admin.register(ForecastPrediction)
class ForecastPredictionAdmin(admin.ModelAdmin):
    list_display = ['forecast_run', 'timestamp', 'predicted_pm25', 'confidence_lower', 'confidence_upper']
    list_filter = ['forecast_run__station__city']
    ordering = ['forecast_run', 'timestamp']
