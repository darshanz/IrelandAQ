#!/bin/bash

set -e

echo "Waiting for database..."
python manage.py wait_for_db

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting development server..."
exec python manage.py runserver 0.0.0.0:8000