import hashlib
import logging
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import jwt
from django.conf import settings

logger = logging.getLogger(__name__)


class EventCreatedFor(StrEnum):
    BOTH = "all"
    TICKET = "tickets"
    TALK = "talk"


def generate_token(request):
    """
    Generate token for video system
    @param request: user request
    @return: jwt
    """
    uid_token = encode_email(request.user.email)
    iat = datetime.now(timezone.utc)
    exp = iat + timedelta(days=30)

    payload = {
        "exp": exp,
        "iat": iat,
        "uid": uid_token,
        "has_permission": check_create_permission(request),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token


def encode_email(email):
    """
    Generate a unique UID token by hashing the email address using SHA-256 and return the first 7 characters.
    @param email: The user's email address.
    @return: The UID token, which consists of the first 7 characters of the hashed email.
    """
    hash_object = hashlib.sha256(email.encode())
    hash_hex = hash_object.hexdigest()
    short_hash = hash_hex[:7]
    return short_hash.upper()


def check_create_permission(request):
    """
    Check if the user has permission to create videos ('can_create_events' permission) and
    has admin session mode (admin session mode has full permissions)
    @param request: user request
    @return: true if the user has permission to create videos or has admin session mode else false
    """
    is_create_permission = (
        "can_create_events"
        in request.user.get_organizer_permission_set(request.organizer)
    )
    is_active_staff_session = request.user.has_active_staff_session(
        request.session.session_key
    )

    if is_create_permission or is_active_staff_session:
        return True
    return False
