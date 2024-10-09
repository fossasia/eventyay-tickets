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

def generate_token(request):
    uid_token = encode_email(request.user.email)
    iat = datetime.now(timezone.utc)
    exp = iat + timedelta(days=30)

    permissions_list = list(request.user.get_organizer_permission_set(request.organizer))
    is_active_staff_session = request.user.has_active_staff_session(request.session.session_key)

    payload = {
        "exp": exp,
        "iat": iat,
        "uid": uid_token,
        "permissions": permissions_list,
        "is_active_staff_session": is_active_staff_session
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


def check_create_permission(request):
    is_create_permission = request.user.get_organizer_permission_set(request.organizer)
    is_active_staff_session= request.user.has_active_staff_session(request.session.session_key)

    if is_create_permission or is_active_staff_session:
        return True
    return False

def create_world(request, is_add_video, data):
    id = data.get('id')
    title = data.get('title')
    timezone = data.get('timezone')
    locale = data.get('locale')

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
