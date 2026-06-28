FROM apache/airflow:3.2.2-python3.13

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
build-essential \
&& rm -rf /var/lib/apt/lists/*


USER airflow

RUN pip install --no-cache-dir \
requests==2.34.2 \
mlflow==3.14.0 \
psycopg2-binary==2.9.12