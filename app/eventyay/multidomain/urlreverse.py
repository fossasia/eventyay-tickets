import datetime
import logging
from typing import cast
from urllib.parse import urljoin, urlsplit

import jwt
from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from eventyay.base.models import Event, Order, OrderPosition, Organizer

from .models import KnownDomain

logger = logging.getLogger(__name__)


def get_event_domain(event, fallback=False, return_info=False):
    assert isinstance(event, Event)
    if event.pk is None:
        # Handle case where event is deleted
        return (None, None) if return_info else None
    suffix = ('_fallback' if fallback else '') + ('_info' if return_info else '')
    domain = getattr(event, '_cached_domain' + suffix, None) or event.cache.get('domain' + suffix)
    if domain is None:
        domain = None, None
        if fallback:
            domains = KnownDomain.objects.filter(
                Q(event=event) | Q(organizer_id=event.organizer_id, event__isnull=True)
            )
            domains_event = [d for d in domains if d.event_id == event.pk]
            domains_org = [d for d in domains if not d.event_id]
            if domains_event:
                domain = domains_event[0].domainname, 'event'
            elif domains_org:
                domain = domains_org[0].domainname, 'organizer'
        else:
            domains = event.domains.all()
            domain = domains[0].domainname if domains else None, 'event'
        event.cache.set('domain' + suffix, domain or 'none')
        setattr(event, '_cached_domain' + suffix, domain or 'none')
    elif domain == 'none':
        setattr(event, '_cached_domain' + suffix, 'none')
        domain = None, None
    else:
        setattr(event, '_cached_domain' + suffix, domain)
    return domain if return_info or not isinstance(domain, tuple) else domain[0]


def get_organizer_domain(organizer):
    assert isinstance(organizer, Organizer)
    domain = getattr(organizer, '_cached_domain', None) or organizer.cache.get('domain')
    if domain is None:
        domains = organizer.domains.filter(event__isnull=True)
        domain = domains[0].domainname if domains else None
        organizer.cache.set('domain', domain or 'none')
        organizer._cached_domain = domain or 'none'
    elif domain == 'none':
        organizer._cached_domain = 'none'
        return None
    else:
        organizer._cached_domain = domain
    return domain


def mainreverse(name, kwargs=None):
    """
    Works similar to ``django.core.urlresolvers.reverse`` but uses the maindomain URLconf even
    if on a subpath.

    Non-keyword arguments are not supported as we want do discourage using them for better
    readability.

    :param name: The name of the URL route
    :type name: str
    :param kwargs: A dictionary of additional keyword arguments that should be used. You do not
        need to provide the organizer or event slug here, it will be added automatically as
        needed.
    :returns: An absolute URL (including scheme and host) as a string
    """
    from eventyay.multidomain import maindomain_urlconf

    kwargs = kwargs or {}
    return reverse(name, kwargs=kwargs, urlconf=maindomain_urlconf)


def eventreverse(obj, name, kwargs=None):
    """
    Works similar to ``django.core.urlresolvers.reverse`` but takes into account that some
    organizers or events might have their own (sub)domain instead of a subpath.

    Non-keyword arguments are not supported as we want do discourage using them for better
    readability.

    :param obj: An ``Event`` or ``Organizer`` object
    :param name: The name of the URL route
    :type name: str
    :param kwargs: A dictionary of additional keyword arguments that should be used. You do not
        need to provide the organizer or event slug here, it will be added automatically as
        needed.
    :returns: An absolute URL (including scheme and host) as a string
    """
    from eventyay.multidomain import (
        event_domain_urlconf,
        maindomain_urlconf,
        organizer_domain_urlconf,
    )

    c = None
    if not kwargs:
        c = obj.cache
        url = c.get('urlrev_{}'.format(name))
        if url:
            return url

    kwargs = kwargs or {}
    if isinstance(obj, Event):
        organizer = obj.organizer
        event = obj
        kwargs['event'] = obj.slug
    elif isinstance(obj, Organizer):
        organizer = obj
        event = None
    else:
        raise TypeError('obj should be Event or Organizer')

    if event:
        domain, domaintype = get_event_domain(obj, fallback=True, return_info=True)
    else:
        domain, domaintype = get_organizer_domain(organizer), 'organizer'

    if domain:
        if domaintype == 'event' and 'event' in kwargs:
            del kwargs['event']
        if 'organizer' in kwargs:
            del kwargs['organizer']

        path = reverse(
            name,
            kwargs=kwargs,
            urlconf=event_domain_urlconf if domaintype == 'event' else organizer_domain_urlconf,
        )
        siteurlsplit = urlsplit(settings.SITE_URL)
        if siteurlsplit.port and siteurlsplit.port not in (80, 443):
            domain = '%s:%d' % (domain, siteurlsplit.port)
        return urljoin('%s://%s' % (siteurlsplit.scheme, domain), path)

    kwargs['organizer'] = organizer.slug
    url = reverse(name, kwargs=kwargs, urlconf=maindomain_urlconf)
    if not kwargs and c:
        c.set('urlrev_{}'.format(url), url)
    return url


def build_absolute_uri(obj, urlname, kwargs=None):
    reversedurl = eventreverse(obj, urlname, kwargs)
    if '://' in reversedurl:
        return reversedurl
    return urljoin(settings.SITE_URL, reversedurl)


def build_join_video_url(event: Event, order: Order) -> str:
    # Get list order position id
    order_product_ids = [position.product_id for position in order.positions.all()]
    # Check if video allow all positions
    if event.settings.venueless_all_products:
        position = order.positions.first()
        return generate_video_token_url_from_order(event, order, position)
    common_product_id = next(
        (product for product in order_product_ids if product in event.settings.venueless_products),
        None,
    )
    # Get position object
    position = order.positions.filter(product_id=common_product_id).first() if common_product_id else None
    # Check if any product in order product is allowed to join
    if any(product in event.settings.venueless_products for product in order_product_ids):
        return generate_video_token_url_from_order(event, order, position)
    logger.error('order %s does not have any product that is allowed to join the event.', order.code)
    # Log more to help debugging
    logger.info('Order products: %s', order_product_ids)
    logger.info('Event allowed products: %s', event.settings.venueless_products)
    return ''


def generate_video_token_url_from_order(event: Event, order: Order, position: OrderPosition | None) -> str:
    # If customer has account, use customer code to generate token
    if hasattr(order, 'customer') and order.customer:
        video_url = generate_video_token_url(event, order.customer.identifier, position)
    else:
        # else user position Id to generate token
        video_url = generate_video_token_url(event, None, position)
    return video_url


def generate_video_token_url(event: Event, customer_code: str, position: OrderPosition | None) -> str:
    iat = datetime.datetime.now(tz=datetime.UTC)
    exp = iat + datetime.timedelta(days=30)
    if not customer_code and not position:
        logger.error('No customer code or position provided for generating video token URL.')
        return ''
    uid = customer_code if customer_code else position.pseudonymization_id
    profile = {'fields': {}}
    if position and position.attendee_name:
        profile['display_name'] = position.attendee_name
    if position and position.company:
        profile['fields']['company'] = position.company

    if position:
        for a in position.answers.filter(question_id__in=event.settings.venueless_questions).select_related('question'):
            profile['fields'][a.question.identifier] = a.answer
    payload = {
        'iss': event.settings.venueless_issuer,
        'aud': event.settings.venueless_audience,
        'exp': exp,
        'iat': iat,
        'uid': uid,
        'profile': profile,
        'traits': list(
            {
                'eventyay-video-event-{}'.format(event.slug),
                'eventyay-video-subevent-{}'.format(position.subevent_id),
                'eventyay-video-product-{}'.format(position.product_id),
                'eventyay-video-variation-{}'.format(position.variation_id),
                'eventyay-video-category-{}'.format(position.product.category_id),
            }
            | {'eventyay-video-product-{}'.format(p.product_id) for p in position.addons.all()}
            | {'eventyay-video-variation-{}'.format(p.variation_id) for p in position.addons.all() if p.variation_id}
            | {
                'eventyay-video-category-{}'.format(p.product.category_id)
                for p in position.addons.all()
                if p.product.category_id
            }
        ),
    }
    token = jwt.encode(payload, event.settings.venueless_secret, algorithm='HS256')
    url = urlsplit(cast(str, event.settings.venueless_url))
    url = url._replace(fragment=f'token={token}')
    return url.geturl()
