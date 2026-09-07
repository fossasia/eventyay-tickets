import logging
import os
from decimal import Decimal
from urllib.parse import urljoin

from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import URLValidator
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from i18nfield.strings import LazyI18nString
from PIL import UnidentifiedImageError

from eventyay.helpers.image_optimize import optimize_uploaded_image

logger = logging.getLogger(__name__)

EVENT_TYPE_SETTING = 'event_type'
MEETUP_EVENT_TYPE = 'meetup'
MEETUP_VIDEO_ACTIVE_SETTING = 'meetup_video_active'

DEFAULT_ROOM_NAME = 'Main Room'
DEFAULT_PRODUCT_NAME = 'RSVP Ticket'
DEFAULT_QUOTA_NAME = 'RSVP'

VIDEO_TYPE_YOUTUBE = 'youtube'
VIDEO_TYPE_HLS = 'hls'

VIDEO_TYPE_CHOICES = [
    ('', _('No video stream')),
    (VIDEO_TYPE_YOUTUBE, _('YouTube')),
    (VIDEO_TYPE_HLS, _('HLS stream')),
]

LOCATION_IN_PERSON = 'in_person'
LOCATION_VIRTUAL = 'virtual'
LOCATION_HYBRID = 'hybrid'
LOCATION_TYPE_CHOICES = [
    (LOCATION_IN_PERSON, _('In-Person')),
    (LOCATION_VIRTUAL, _('Virtual')),
    (LOCATION_HYBRID, _('Both (Hybrid)')),
]

CAPACITY_UNLIMITED = 'unlimited'
CAPACITY_LIMITED = 'limited'
CAPACITY_TYPE_CHOICES = [
    (CAPACITY_UNLIMITED, _('Unlimited')),
    (CAPACITY_LIMITED, _('Limited')),
]

REGISTRATION_FEE_FREE = 'free'
REGISTRATION_FEE_PAID = 'paid'
REGISTRATION_FEE_CHOICES = [
    (REGISTRATION_FEE_FREE, _('Free')),
    (REGISTRATION_FEE_PAID, _('Paid')),
]

PRIVACY_PUBLIC = 'public'
PRIVACY_PRIVATE = 'private'
PRIVACY_CHOICES = [
    (PRIVACY_PUBLIC, _('Public')),
    (PRIVACY_PRIVATE, _('Private')),
]

VIDEO_MODULES = {
    VIDEO_TYPE_YOUTUBE: ('livestream.youtube', 'ytid'),
    VIDEO_TYPE_HLS: ('livestream.native', 'hls_url'),
}

VIDEO_TYPES_BY_MODULE = {
    module_type: (video_type, config_key) for video_type, (module_type, config_key) in VIDEO_MODULES.items()
}

URL_VIDEO_TYPES = (VIDEO_TYPE_HLS,)

LIVESTREAM_MODULE_PREFIX = 'livestream.'

VIDEO_SETTINGS_KEYS = (
    'venueless_url',
    'venueless_issuer',
    'venueless_audience',
    'venueless_secret',
)


def is_meetup_event(event) -> bool:
    if event is None:
        return False
    return event.settings.get(EVENT_TYPE_SETTING) == MEETUP_EVENT_TYPE


def get_video_module_config(video_type, video_url):
    if not video_type or video_type not in VIDEO_MODULES:
        return []
    module_type, config_key = VIDEO_MODULES[video_type]
    return [{'type': module_type, 'config': {config_key: video_url}}]


def get_video_config_from_modules(module_config) -> dict:
    try:
        entry = (module_config or [])[0]
        module_type = entry.get('type')
        config = entry.get('config') or {}
    except (IndexError, AttributeError, KeyError, TypeError):
        return {}
    if module_type not in VIDEO_TYPES_BY_MODULE:
        return {}
    video_type, config_key = VIDEO_TYPES_BY_MODULE[module_type]
    return {'video_type': video_type, 'video_url': config.get(config_key, '')}


def _is_video_module(module) -> bool:
    module_type = (module or {}).get('type', '') or ''
    return module_type.startswith(LIVESTREAM_MODULE_PREFIX)


def has_video_stream(event) -> bool:
    with scope(event=event):
        return any(
            _is_video_module(module)
            for room in event.rooms.filter(deleted=False)
            for module in room.module_config or []
        )


def get_main_room(event):
    from eventyay.base.models.room import Room

    with scope(event=event):
        return Room.objects.filter(event=event, deleted=False).first()


def get_video_config_initial(event) -> dict:
    room = get_main_room(event)
    if not room:
        return {}
    return get_video_config_from_modules(room.module_config)


def sync_meetup_room(event, module_config):
    from eventyay.base.models.room import Room

    with scope(event=event):
        room = Room.objects.filter(event=event, deleted=False).first()
        if room is None:
            locale = getattr(event, 'locale', 'en') or 'en'
            room = Room(
                event=event,
                name=LazyI18nString({locale: DEFAULT_ROOM_NAME}),
                deleted=False,
            )
        room.module_config = module_config
        room.save()
        return room


def build_video_form_fields(type_help_text=None) -> dict:
    return {
        'video_type': forms.ChoiceField(
            choices=VIDEO_TYPE_CHOICES,
            required=False,
            label=_('Video stream type'),
            help_text=type_help_text or _('Configure a live video stream for this meetup.'),
        ),
        'video_url': forms.CharField(
            required=False,
            max_length=255,
            label=_('Video URL / stream identifier'),
            help_text=_('YouTube video URL or HLS stream URL.'),
        ),
    }


def validate_video_fields(video_type, video_url) -> dict:
    errors = {}
    if video_type and not video_url:
        errors['video_url'] = _('A URL is required when a video type is selected.')
    if video_url and not video_type:
        errors['video_type'] = _('A video type is required when a URL is provided.')
    if video_url and video_type in URL_VIDEO_TYPES:
        try:
            URLValidator()(video_url)
        except ValidationError:
            errors['video_url'] = _('Enter a valid URL.')
    return errors


def add_video_field_errors(form, video_type, video_url):
    for field, message in validate_video_fields(video_type, video_url).items():
        form.add_error(field, message)


def apply_video_configuration(event, video_type, video_url):
    module_config = get_video_module_config(video_type, video_url)
    event.settings.set(MEETUP_VIDEO_ACTIVE_SETTING, bool(module_config))
    sync_meetup_room(event, module_config)
    return module_config


def _has_video_credentials(event) -> bool:
    return all(event.settings.get(key) for key in VIDEO_SETTINGS_KEYS)


def _jwt_config(event) -> dict:
    config = event.config or {}
    if not config.get('JWT_secrets'):
        config['JWT_secrets'] = [
            {
                'issuer': 'any',
                'audience': 'eventyay',
                'secret': get_random_string(length=64),
            }
        ]
        event.config = config
        event.save(update_fields=['config'])
    return event.config['JWT_secrets'][0]


def build_video_base_url(event, request=None) -> str:
    if request is not None:
        scheme = 'https' if request.is_secure() else 'http'
        return f'{scheme}://{request.get_host()}{event.urls.video_base}'
    site_url = getattr(django_settings, 'SITE_URL', 'http://localhost:8000')
    return urljoin(site_url, event.urls.video_base)


def _write_video_credentials(event, request=None):
    jwt_config = _jwt_config(event)
    event.settings.set('venueless_secret', jwt_config['secret'])
    event.settings.set('venueless_issuer', jwt_config['issuer'])
    event.settings.set('venueless_audience', jwt_config['audience'])
    event.settings.set('venueless_all_products', True)
    event.settings.set('venueless_show_public_link', True)
    event.settings.set('venueless_url', build_video_base_url(event, request))


def ensure_video_credentials(event, request=None, force=False) -> bool:
    from eventyay.base.models import Event

    if not force and _has_video_credentials(event):
        return False

    if force:
        _write_video_credentials(event, request)
        return True

    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        if _has_video_credentials(locked_event):
            return False
        _write_video_credentials(locked_event, request)
        locked_event.settings.flush()
    event.settings.flush()
    return True


def ensure_rsvp_product(event, price=None):
    """
    Ensure an active admission product and quota exist for a meetup event.

    Note: Product and Quota models in Eventyay are scoped by organizer
    (`event__organizer`) in the ORM, so this helper establishes organizer
    scope internally. Callers should not wrap calls to this helper in
    redundant `scope(organizer=...)` blocks.
    """
    from eventyay.base.models import Quota
    from eventyay.base.models.product import Product

    locale = getattr(event, 'locale', 'en') or 'en'
    fee_price = price if price is not None else Decimal('0.00')
    with scope(organizer=event.organizer):
        product = event.products.filter(admission=True, active=True).first()
        if product is None:
            product = Product(
                event=event,
                name=LazyI18nString({locale: DEFAULT_PRODUCT_NAME}),
                default_price=fee_price,
                admission=True,
                active=True,
            )
            product.save()
        elif price is not None and product.default_price != fee_price:
            product.default_price = fee_price
            product.save(update_fields=['default_price'])

        quota = product.quotas.first()
        if quota is None:
            quota = event.quotas.filter(name=DEFAULT_QUOTA_NAME).first()
        if quota is None:
            quota = Quota(event=event, name=DEFAULT_QUOTA_NAME, size=None)
            quota.save()
        quota.products.add(product)
        return product, quota


def get_rsvp_product_and_quota(event):
    """
    Retrieve the active RSVP product and associated quota for a meetup event.

    Note: Product and Quota models in Eventyay are scoped by organizer
    (`event__organizer`) in the ORM, so this helper establishes organizer
    scope internally. Callers should not wrap calls to this helper in
    redundant `scope(organizer=...)` blocks.
    """
    with scope(organizer=event.organizer):
        product = event.products.filter(admission=True, active=True).first()
        if product is None:
            return None, None
        quota = product.quotas.first()
        return product, quota


def _save_meetup_header_image(event, header_image, crop_box=None):
    if not isinstance(header_image, UploadedFile):
        return

    setting_key = 'logo_image'
    try:
        result = optimize_uploaded_image(header_image, setting_key, crop_box=crop_box)
    except (OSError, ValueError, UnidentifiedImageError):
        logger.warning('Could not optimize uploaded header image for event %s', event.slug, exc_info=True)
        header_image.seek(0)
        result = None

    nonce = get_random_string(length=8)
    clean_name, _ = os.path.splitext(header_image.name or setting_key)
    base_path = f'pub/{event.organizer.slug}/{event.slug}/{clean_name}.{nonce}'

    if result:
        optimized_name = f'{base_path}.{result.optimized_ext}'
        optimized_path = default_storage.save(optimized_name, result.optimized)
        original_name = f'{base_path}_original.{result.original_ext}'
        try:
            default_storage.save(original_name, result.original)
            event.settings.set(f'{setting_key}_original_ext', result.original_ext)
        except OSError:
            pass
        event.settings.set(setting_key, f'file://{optimized_path}')
    else:
        ext = os.path.splitext(header_image.name)[1] if header_image.name else '.jpg'
        file_path = default_storage.save(f'{base_path}{ext}', header_image)
        event.settings.set(setting_key, f'file://{file_path}')


def set_meetup_privacy(event, is_private: bool):
    """Configure meetup visibility flags for public or private operation."""
    with transaction.atomic():
        event.live = True
        event.tickets_published = True
        event.private_testmode = False
        event.is_public = not is_private
        event.startpage_visible = not is_private
        if is_private:
            event.startpage_featured = False
        event.settings.set('private_testmode_tickets', False)
        event.settings.set('meta_noindex', is_private)
        event.save(update_fields=['live', 'tickets_published', 'private_testmode', 'is_public', 'startpage_visible', 'startpage_featured'])


def provision_meetup_event(
    event,
    video_type='',
    video_url='',
    request=None,
    frontpage_text=None,
    header_image=None,
    registration_limit=None,
    crop_box=None,
    registration_fee=None,
    payment_stripe_publishable_key='',
    payment_stripe_secret_key='',
    payment_stripe_merchant_country='',
    is_private=False,
):
    event.settings.set(EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE)
    set_meetup_privacy(event, is_private=is_private)

    if frontpage_text is not None:
        event.settings.set('frontpage_text', frontpage_text)

    if header_image:
        _save_meetup_header_image(event, header_image, crop_box=crop_box)

    ensure_video_credentials(event, request=request, force=True)
    apply_video_configuration(event, video_type, video_url)

    fee_decimal = Decimal(str(registration_fee)) if registration_fee else Decimal('0.00')
    product, quota = ensure_rsvp_product(event, price=fee_decimal)

    if fee_decimal > Decimal('0.00') and payment_stripe_secret_key:
        event.settings.set('payment_stripe__enabled', True)
        if payment_stripe_publishable_key:
            event.settings.set('payment_stripe_publishable_key', payment_stripe_publishable_key)
        if payment_stripe_secret_key:
            event.settings.set('payment_stripe_secret_key', payment_stripe_secret_key)
        if payment_stripe_merchant_country:
            event.settings.set('payment_stripe_merchant_country', payment_stripe_merchant_country)

    if quota and registration_limit is not None:
        with scope(organizer=event.organizer):
            quota.size = registration_limit
            quota.save(update_fields=['size'])

    acting_user = request.user if request and getattr(request, 'user', None) and request.user.is_authenticated else None
    event.log_action(
        'eventyay.event.meetup.created',
        user=acting_user,
        data={
            'video_type': video_type,
            'video_url': video_url,
            'registration_fee': str(fee_decimal),
            'is_private': is_private,
        },
    )
