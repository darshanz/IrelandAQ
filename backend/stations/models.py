from django.contrib.gis.db import models as gis_models
from django.db import models
import datetime

class Station(models.Model):
    """
    An air quality monitoring station
    """

    openaq_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length = 200)
    city = models.CharField(max_length = 100)
    country = models.CharField(max_length = 10, default='IE')
    location = gis_models.PointField(geography=True, srid=4326)
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['city', 'name']

    def __str__(self):
        return f"{self.name} ({self.city})"


class AirQualityReading(models.Model):
    station = models.ForeignKey(Station,
                                on_delete=models.CASCADE,
                                related_name='readings',)

    timestamp = models.DateTimeField(db_index=True)

    # pollutant concetrations
    pm25 = models.FloatField(null=True, blank=True)
    pm10 = models.FloatField(null=True, blank=True)
    no2 = models.FloatField(null=True, blank=True)
    o3 = models.FloatField(null=True, blank=True)
    co = models.FloatField(null=True, blank=True)

    aqi = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        unique_together = ['station', 'timestamp']

    def __str__(self):
        return f"{self.station.name} @ {self.timestamp:%Y-%m-%d %H:%M}"

