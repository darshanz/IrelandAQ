#!/bin/bash

set -e

echo "Waiting for database..."
python manage.py wait_for_db

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating superuser..."
python manage.py createsuperuser --noinput || true

echo "Seeding stations..."
python manage.py seed_stations --with-readings

echo "Starting development server..."
exec python manage.py runserver 0.0.0.0:8000