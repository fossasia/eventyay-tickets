#!/bin/bash
# Start server
echo "Starting server"
exec celery worker -A venueless.celery_app -l info
