#!/bin/bash
# Apply database migrations
echo "Apply database migrations"
python manage.py migrate

# Start server
echo "Starting server"
exec python manage.py runserver 0.0.0.0:8375
