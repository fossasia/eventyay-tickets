import hashlib
import random
import string
from datetime import datetime, timezone, timedelta
import jwt
import requests
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

## Generate token for video system
def generate_token(request):
    uid_token = encode_email(request.user.email)
    iat = datetime.now(timezone.utc)
    exp = iat + timedelta(days=30)

    payload = {
        "exp": exp,
        "iat": iat,
        "uid": uid_token,
        "has_permission": check_create_permission(request),
    }
    token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm="HS256"
    )
    return token


def encode_email(email):
    hash_object = hashlib.sha256(email.encode())
    hash_hex = hash_object.hexdigest()
    short_hash = hash_hex[:7]
    characters = string.ascii_letters + string.digits
    random_suffix = ''.join(random.choice(characters) for _ in range(7 - len(short_hash)))
    final_result = short_hash + random_suffix
    return final_result.upper()

## Check if the user has permission to create videos ('can_create_events' permission) and has admin session mode (admin session mode has full permissions)
def check_create_permission(request):
    is_create_permission = 'can_create_events' in request.user.get_organizer_permission_set(request.organizer)
    is_active_staff_session= request.user.has_active_staff_session(request.session.session_key)

    if is_create_permission or is_active_staff_session:
        return True
    return False

## user create automatically world when choosing add video option in create ticket form
def create_world(request, is_add_video, data):
    id = data.get('id')
    title = data.get('title')
    timezone = data.get('timezone')
    locale = data.get('locale')

    ## check if user choose add video option and has permission to create video system ('can_create_events' permission)
    if is_add_video and check_create_permission(request):
        try:
            requests.post("{}/api/v1/create-world/".format(settings.VIDEO_SERVER_HOSTNAME), json={
                "id": id,
                "title": title,
                "timezone": timezone,
                "locale": locale,
            }, headers={
                "Authorization": "Bearer " + generate_token(request)
            })
        except requests.exceptions.RequestException as e:
            logger.error('An error occurred while requesting to create a video: %s' % e)
            messages.error(request, _('Cannot create video system for this event. Please try again later.'))
    elif is_add_video and not check_create_permission(request):
        messages.error(request, _('You do not have permission to create video system'))
