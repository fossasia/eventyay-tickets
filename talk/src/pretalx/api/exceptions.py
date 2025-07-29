import json
import logging

from rest_framework import exceptions
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, exceptions.APIException):
        logger.debug(f"API Exception [{exc.status_code}]: {json.dumps(exc.detail)}")

    return response
