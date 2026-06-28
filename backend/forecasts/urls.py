from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'forecasts', views.ForecastViewSet, basename='forecast')

# APiView instance need to be added separately
urlpatterns = router.urls + [
    path(
        'mlflow-models/',
        views.MLflowModelsView.as_view(),
        name='mlflow-models',
    ),
]