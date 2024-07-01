import warnings
import time
from importlib import import_module
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import resolve
from django.utils.crypto import constant_time_compare
from django.utils.functional import SimpleLazyObject
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.defaults import permission_denied
from django_scopes import scope

from pretix.base.middleware import LocaleMiddleware
from pretix.base.models import Event, Organizer, Customer
from pretix.multidomain.urlreverse import (
    get_event_domain, get_organizer_domain,
)
from pretix.presale.signals import process_request, process_response

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


def get_customer(request):
    """
    Retrieves the currently authenticated customer from the request.

    This function checks if the customer is already cached in the request. If not, it attempts to
    retrieve the customer from the session using the organizer's primary key and validates the
    session hash to ensure the customer is authenticated. If the customer cannot be found or the
    session hash does not match, it returns None.

    Args:
        request (HttpRequest): The HTTP request object containing session and organizer information.

    Returns:
        Customer or None: The authenticated customer if found and verified, otherwise None.
    """
    # Check if the customer is already cached in the request
    if not hasattr(request, '_cached_customer'):
        # Generate session keys based on the organizer's primary key
        session_key = f'customer_auth_id:{request.organizer.pk}'
        hash_session_key = f'customer_auth_hash:{request.organizer.pk}'

        with scope(organizer=request.organizer):
            try:
                # Attempt to retrieve the customer from the organizer's customer list
                customer = request.organizer.customers.get(
                    Q(provider__isnull=True) | Q(provider__is_active=True),
                    is_active=True, is_verified=True,
                    pk=request.session[session_key]
                )
            except (Customer.DoesNotExist, KeyError):
                # If the customer does not exist or the session key is not found, set cached customer to None
                request._cached_customer = None
            else:
                # Retrieve the session hash from the session
                session_hash = request.session.get(hash_session_key)
                session_hash_verified = session_hash and constant_time_compare(
                    session_hash,
                    customer.get_session_auth_hash()
                )
                if session_hash_verified:
                    # If the session hash is verified, cache the customer in the request
                    request._cached_customer = customer
                else:
                    # If the session hash is not verified, flush the session and set cached customer to None
                    request.session.flush()
                    request._cached_customer = None

    # Return the cached customer
    return request._cached_customer


def update_customer_session_auth_hash(request, customer):
    hash_session_key = f'customer_auth_hash:{request.organizer.pk}'
    session_auth_hash = customer.get_session_auth_hash()
    request.session.cycle_key()
    request.session[hash_session_key] = session_auth_hash


def add_customer_to_request(request):
    request.customer = SimpleLazyObject(lambda: get_customer(request))


def get_customer_auth_time(request):
    auth_time_session_key = f'customer_auth_time:{request.organizer.pk}'
    return request.session.get(auth_time_session_key) or 0


def customer_login(request, customer):
    """
    Logs in a customer by setting appropriate session variables and updating their last login time.

    This function handles the process of logging a customer into the system by setting various session
    keys, ensuring session security, and updating the customer's last login timestamp. It also handles
    session key cycling and token rotation to enhance security.

    Args:
        request (HttpRequest): The HTTP request object containing session and organizer information.
        customer (Customer): The customer object that is being logged in.

    Returns:
        None
    """
    # Define session keys based on the organizer's primary key
    session_key = f'customer_auth_id:{request.organizer.pk}'
    hash_session_key = f'customer_auth_hash:{request.organizer.pk}'
    auth_time_session_key = f'customer_auth_time:{request.organizer.pk}'

    # Generate the session authentication hash for the customer
    session_auth_hash = customer.get_session_auth_hash()

    # Check if the session already contains a customer authentication ID
    if session_key in request.session:
        # If the current session customer ID does not match the given customer ID, or
        # if the session hash does not match the customer's session hash, flush the session
        if request.session[session_key] != customer.pk or (
                not constant_time_compare(request.session.get(hash_session_key, ''), session_auth_hash)):
            request.session.flush()
    else:
        # Cycle the session key to prevent fixation attacks
        request.session.cycle_key()

    # Set the session variables for the authenticated customer
    request.session[session_key] = customer.pk
    request.session[hash_session_key] = session_auth_hash
    request.session[auth_time_session_key] = int(time.time())

    # Attach the customer object to the request
    request.customer = customer

    # Update the last login time of the customer
    customer.last_login = now()
    customer.save(update_fields=['last_login'])

    # Rotate the CSRF token to enhance security
    rotate_token(request)


def customer_logout(request):
    """
    Logs out the customer by clearing their session variables and resetting the session state.

    This function handles the process of logging out a customer by removing their session data,
    clearing any customer-related information from the session, and rotating the session key
    and CSRF token for security purposes.

    Args:
        request (HttpRequest): The HTTP request object containing session and organizer information.

    Returns:
        None
    """
    # Define session keys based on the organizer's primary key
    session_key = f'customer_auth_id:{request.organizer.pk}'
    hash_session_key = f'customer_auth_hash:{request.organizer.pk}'
    auth_time_session_key = f'customer_auth_time:{request.organizer.pk}'

    # Remove customer-specific session variables
    customer_id = request.session.pop(session_key, None)
    request.session.pop(hash_session_key, None)
    request.session.pop(auth_time_session_key, None)

    # Clear customer-related information from the carts in the session
    carts = request.session.get('carts', {})
    for k, v in list(carts.items()):
        if v.get('customer') == customer_id:
            carts.pop(k)
    request.session['carts'] = carts

    # Cycle the session key to prevent fixation attacks
    request.session.cycle_key()

    # Rotate the CSRF token to enhance security
    rotate_token(request)

    # Clear customer-related attributes from the request
    request.customer = None
    request._cached_customer = None


@scope(organizer=None)
def _detect_event(request, require_live=True, require_plugin=None):
    if hasattr(request, '_event_detected'):
        return

    db = 'default'
    if request.method == 'GET':
        db = settings.DATABASE_REPLICA

    url = resolve(request.path_info)

    try:
        if hasattr(request, 'event_domain'):
            # We are on an event's custom domain
            pass
        elif hasattr(request, 'organizer_domain'):
            # We are on an organizer's custom domain
            if 'organizer' in url.kwargs and url.kwargs['organizer']:
                if url.kwargs['organizer'] != request.organizer.slug:
                    raise Http404(_('The selected event was not found.'))
                path = "/" + request.get_full_path().split("/", 2)[-1]
                return redirect(path)

            request.event = request.organizer.events.using(db).get(
                slug=url.kwargs['event'],
                organizer=request.organizer,
            )
            request.organizer = request.organizer

            # If this event has a custom domain, send the user there
            domain = get_event_domain(request.event)
            if domain:
                if request.port and request.port not in (80, 443):
                    domain = '%s:%d' % (domain, request.port)
                path = request.get_full_path().split("/", 2)[-1]
                r = redirect(urljoin('%s://%s' % (request.scheme, domain), path))
                r['Access-Control-Allow-Origin'] = '*'
                return r
        else:
            # We are on our main domain
            if 'event' in url.kwargs and 'organizer' in url.kwargs:
                request.event = Event.objects \
                    .select_related('organizer') \
                    .using(db) \
                    .get(
                    slug=url.kwargs['event'],
                    organizer__slug=url.kwargs['organizer']
                )
                request.organizer = request.event.organizer

                domain = get_event_domain(request.event)
                if domain:
                    if request.port and request.port not in (80, 443):
                        domain = '%s:%d' % (domain, request.port)
                    path = request.get_full_path().split("/", 3)[-1]
                    r = redirect(urljoin('%s://%s' % (request.scheme, domain), path))
                    r['Access-Control-Allow-Origin'] = '*'
                    return r
            elif 'organizer' in url.kwargs:
                request.organizer = Organizer.objects.using(db).get(
                    slug=url.kwargs['organizer']
                )
            else:
                raise Http404()

            domain = get_organizer_domain(request.organizer)
            if domain:
                if request.port and request.port not in (80, 443):
                    domain = '%s:%d' % (domain, request.port)
                path = request.get_full_path().split("/", 2)[-1]
                r = redirect(urljoin('%s://%s' % (request.scheme, domain), path))
                r['Access-Control-Allow-Origin'] = '*'
                return r
        if not hasattr(request, 'customer'):
            add_customer_to_request(request)
        if hasattr(request, 'event'):
            LocaleMiddleware(NotImplementedError).process_request(request)

            if require_live and not request.event.live:
                can_access = (
                        url.url_name == 'event.auth'
                        or (
                                request.user.is_authenticated
                                and request.user.has_event_permission(request.organizer, request.event, request=request)
                        )

                )
                if not can_access and 'pretix_event_access_{}'.format(request.event.pk) in request.session:
                    sparent = SessionStore(request.session.get('pretix_event_access_{}'.format(request.event.pk)))
                    try:
                        parentdata = sparent.load()
                    except:
                        pass
                    else:
                        can_access = 'event_access' in parentdata

                if not can_access:
                    return permission_denied(
                        request, PermissionDenied(_('The selected ticket shop is currently not available.'))
                    )

            if require_plugin:
                is_core = any(require_plugin.startswith(m) for m in settings.CORE_MODULES)
                if require_plugin not in request.event.get_plugins() and not is_core:
                    raise Http404(_('This feature is not enabled.'))

            for receiver, response in process_request.send(request.event, request=request):
                if response:
                    return response

    except Event.DoesNotExist:
        try:
            if hasattr(request, 'organizer_domain'):
                event = request.organizer.events.get(
                    slug__iexact=url.kwargs['event'],
                    organizer=request.organizer,
                )
                pathparts = request.get_full_path().split('/')
                pathparts[1] = event.slug
                return redirect('/'.join(pathparts))
            else:
                if 'event' in url.kwargs and 'organizer' in url.kwargs:
                    event = Event.objects.select_related('organizer').get(
                        slug__iexact=url.kwargs['event'],
                        organizer__slug__iexact=url.kwargs['organizer']
                    )
                    pathparts = request.get_full_path().split('/')
                    pathparts[1] = event.organizer.slug
                    pathparts[2] = event.slug
                    return redirect('/'.join(pathparts))
        except Event.DoesNotExist:
            raise Http404(_('The selected event was not found.'))
        raise Http404(_('The selected event was not found.'))
    except Organizer.DoesNotExist:
        if 'organizer' in url.kwargs:
            try:
                organizer = Organizer.objects.get(
                    slug__iexact=url.kwargs['organizer']
                )
            except Organizer.DoesNotExist:
                raise Http404(_('The selected organizer was not found.'))
            pathparts = request.get_full_path().split('/')
            pathparts[1] = organizer.slug
            return redirect('/'.join(pathparts))
        raise Http404(_('The selected organizer was not found.'))

    request._event_detected = True


def _event_view(function=None, require_live=True, require_plugin=None):
    def event_view_wrapper(func, require_live=require_live):
        def wrap(request, *args, **kwargs):
            ret = _detect_event(request, require_live=require_live, require_plugin=require_plugin)
            if ret:
                return ret
            else:
                with scope(organizer=getattr(request, 'organizer', None)):
                    response = func(request=request, *args, **kwargs)
                    for receiver, r in process_response.send(request.event, request=request, response=response):
                        response = r

                    if isinstance(response, TemplateResponse):
                        response = response.render()

                    return response

        for attrname in dir(func):
            # Preserve flags like csrf_exempt
            if not attrname.startswith('__'):
                setattr(wrap, attrname, getattr(func, attrname))
        return wrap

    if function:
        return event_view_wrapper(function, require_live=require_live)
    return event_view_wrapper


def event_view(function=None, require_live=True):
    warnings.warn('The event_view decorator is deprecated since it will be automatically applied by the URL routing '
                  'layer when you use event_urls.',
                  DeprecationWarning)

    def noop(fn):
        return fn

    return function or noop
