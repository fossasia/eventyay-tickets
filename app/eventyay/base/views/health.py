from django.conf import settings
from django.core import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import logging

from ..models import User

logger = logging.getLogger(__name__)


def healthcheck(request):
    # Perform a simple DB query to see that DB access works
    User.objects.exists()

    # Test if redis access works
    if settings.HAS_REDIS:
        import django_redis

        redis = django_redis.get_redis_connection('redis')
        redis.set('_healthcheck', 1)
        if not redis.exists('_healthcheck'):
            return HttpResponse('Redis not available.', status=503)

    cache.cache.set('_healthcheck', '1')
    if not cache.cache.get('_healthcheck') == '1':
        return HttpResponse('Cache not available.', status=503)

    return HttpResponse()


@csrf_exempt
@require_POST
def csp_report(request):
    """
    Handle Content Security Policy violation reports.
    """
    try:
        if request.content_type == 'application/csp-report':
            report_data = json.loads(request.body.decode('utf-8'))
            if settings.LOG_CSP and settings.DEBUG:
                logger.warning('CSP Violation Report: %s', json.dumps(report_data, indent=2))
        return HttpResponse(status=204)  # No Content
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        if settings.DEBUG:
            logger.error('Failed to parse CSP report: %s', str(e))
        return HttpResponse(status=400)  # Bad Request
    except Exception as e:
        if settings.DEBUG:
            logger.error('Error processing CSP report: %s', str(e))
        return HttpResponse(status=500)  # Internal Server Error
