# IrelandAQ

![Status](https://img.shields.io/badge/status-work%20in%20progress-orange)
![Python](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/django-6.0.6-092E20?logo=django&logoColor=white)
![Airflow](https://img.shields.io/badge/airflow-3.2.2-017CEE?logo=apacheairflow&logoColor=white)
![MLflow](https://img.shields.io/badge/mlflow-3.14.0-0194E2?logo=mlflow&logoColor=white)
![PostGIS](https://img.shields.io/badge/postgis-18--3.6-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)

Air quality monitoring and forecasting platform for Ireland, built with Django, Apache Airflow, and MLflow.

![architecture.png](architecture.png)

## Stack

- **Django + PostGIS** — REST API and station data
- **Airflow** — hourly ingestion from [OpenAQ v3](https://api.openaq.org)
- **MLflow** — model tracking and registry
- **Docker Compose** — local development
-  **Next.js** — frontend

## Quick start

```bash
cp .env.example .env   # fill in OPENAQ_API_KEY and secrets
docker compose up -d
```

Django runs at `http://localhost:8000`, Airflow at `http://localhost:8080`.
