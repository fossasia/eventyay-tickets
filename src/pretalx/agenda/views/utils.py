import hashlib
import random
import string
from contextlib import suppress

from pretalx.common.signals import register_data_exporters, register_my_data_exporters


def is_visible(exporter, request, public=False):
    if not public:
        return request.user.has_perm("orga.view_schedule", request.event)
    if not request.user.has_perm("agenda.view_schedule", request.event):
        return False
    if hasattr(exporter, "is_public"):
        with suppress(Exception):
            return exporter.is_public(request=request)
    return exporter.public


def get_schedule_exporters(request, public=False):
    exporters = [
        exporter(request.event)
        for _, exporter in register_data_exporters.send_robust(request.event)
    ]
    my_exporters = [
        exporter(request.event)
        for _, exporter in register_my_data_exporters.send_robust(request.event)
    ]
    all_exporters = exporters + my_exporters
    return [
        exporter
        for exporter in all_exporters
        if (
            not isinstance(exporter, Exception)
            and is_visible(exporter, request, public=public)
        )
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
    random_suffix = "".join(
        random.choice(characters) for _ in range(7 - len(short_hash))
    )
    final_result = short_hash + random_suffix
    return final_result.upper()
