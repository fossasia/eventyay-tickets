import hashlib
import random
import string
import logging
from contextlib import suppress

from django.http import HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.utils.translation import activate

from eventyay.common.signals import register_data_exporters, register_my_data_exporters
from eventyay.common.text.path import safe_filename
from eventyay.base.models.submission import SubmissionFavouriteDeprecated

logger = logging.getLogger(__name__)


def is_visible(exporter, request, public=False):
    if not public:
        return request.user.is_authenticated
    if not request.user.has_perm('base.list_schedule', request.event):
        return False
    if hasattr(exporter, 'is_public'):
        with suppress(Exception):
            return exporter.is_public(request=request)
    return exporter.public


def get_schedule_exporters(request, public=False):
    exporters = [exporter(request.event) for _, exporter in register_data_exporters.send_robust(request.event)]
    my_exporters = [exporter(request.event) for _, exporter in register_my_data_exporters.send_robust(request.event)]
    all_exporters = exporters + my_exporters
    return [
        exporter
        for exporter in all_exporters
        if (not isinstance(exporter, Exception) and is_visible(exporter, request, public=public))
    ]


def find_schedule_exporter(request, name, public=False):
    for exporter in get_schedule_exporters(request, public=public):
        if exporter.identifier == name:
            return exporter
    return None


def encode_email(email):
    """
    Encode email to a short hash and get first 7 characters
    @param email: User's email
    @return: encoded string
    """
    hash_object = hashlib.sha256(email.encode())
    hash_hex = hash_object.hexdigest()
    short_hash = hash_hex[:7]
    characters = string.ascii_letters + string.digits
    random_suffix = ''.join(random.choice(characters) for _ in range(7 - len(short_hash)))
    final_result = short_hash + random_suffix
    return final_result.upper()


def get_schedule_exporter_content(request, exporter_name, schedule):
    is_organizer = request.user.has_perm('base.orga_view_schedule', request.event)
    exporter = find_schedule_exporter(request, exporter_name, public=not is_organizer)
    if not exporter:
        return
    exporter.schedule = schedule
    exporter.is_orga = is_organizer
    lang_code = request.GET.get('lang')
    if lang_code and lang_code in request.event.locales:
        activate(lang_code)
    elif 'lang' in request.GET:
        activate(request.event.locale)
    exporter.schedule = schedule
    if '-my' in exporter.identifier and request.user.id is None:
        if request.GET.get('talks'):
            exporter.talk_ids = request.GET.get('talks').split(',')
        else:
            return HttpResponseRedirect(request.event.urls.login)
    favs_talks = SubmissionFavouriteDeprecated.objects.filter(user=request.user.id)
    if favs_talks.exists():
        exporter.talk_ids = favs_talks[0].talk_list
    try:
        file_name, file_type, data = exporter.render(request=request)
        etag = hashlib.sha1(str(data).encode()).hexdigest()
    except Exception:
        logger.exception(f'Failed to use {exporter.identifier} for {request.event.slug}')
        return
    if request.headers.get('If-None-Match') == etag:
        return HttpResponseNotModified()
    headers = {'ETag': f'"{etag}"'}
    if file_type not in ('application/json', 'text/xml'):
        headers['Content-Disposition'] = f'attachment; filename="{safe_filename(file_name)}"'
    if exporter.cors:
        headers['Access-Control-Allow-Origin'] = exporter.cors
    return HttpResponse(data, content_type=file_type, headers=headers)
