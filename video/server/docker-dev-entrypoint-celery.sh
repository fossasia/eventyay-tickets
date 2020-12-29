#!/bin/bash
# Start server
echo "Starting server"
exec celery -A venueless.celery_app worker -l info
