from django.contrib.gis import admin
from .models import Station, AirQualityReading


@admin.register(Station)
class StationAdmin(admin.GISModelAdmin):
    list_display= ['name', 'city', 'openaq_id', 'is_active', 'last_updated']
    list_filter= ['city', 'is_active', 'country']
    search_fields = ['name', 'city', 'openaq_id']
    ordering  = ['city', 'name']


@admin.register(AirQualityReading)
class AirQualityReadingAdmin(admin.ModelAdmin):
    list_display= ['station', 'timestamp', 'pm25', 'pm10', 'no2', 'aqi']
    list_filter= ['station__city']
    search_fields = ['station__name']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']