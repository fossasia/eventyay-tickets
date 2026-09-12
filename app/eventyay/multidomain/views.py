import json
import logging
import os
from mimetypes import guess_type
from urllib.parse import quote
from urllib.request import urlopen

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.utils.timezone import now
from django.utils.translation import gettext as _, pgettext
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import View
from django.views.static import serve as static_serve
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.agenda.views.utils import build_public_schedule_exporters
from eventyay.base.models import Event
from eventyay.base.models.room import AnonymousInvite
from eventyay.base.services.video_theme import build_video_theme_for_event
from eventyay.common.language import get_ui_language_options
from eventyay.common.templatetags.vite import fetch_vite_html, VIDEO_DIST_DIR, VIDEO_DEV_SERVER
from eventyay.consts import SizeKey
from eventyay.eventyay_common.video.traits_sync import check_has_active_staff_session

logger = logging.getLogger(__name__)


def safe_reverse(name: str, **kw) -> str:
    try:
        return reverse(name, kwargs=kw) if kw else reverse(name)
    except NoReverseMatch as e:
        logger.warning('Video SPA: Could not reverse %s with %s: %s', name, kw, e)
        return '/missing-url-registration/'


class VideoSPAView(View):
    is_organizer = False

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *args, **kwargs):
        organizer_slug = kwargs.get('organizer')
        event_slug = kwargs.get('event')
        event_identifier = kwargs.get('event_identifier')

        event = None
        if organizer_slug and event_slug:
            try:
                event = Event.objects.select_related('organizer').get(slug=event_slug, organizer__slug=organizer_slug)
            except Event.DoesNotExist:
                return HttpResponse('Event not found', status=404)

        if self.is_organizer and event:
            if not request.user.is_authenticated:
                login_url = safe_reverse('auth.login')
                return redirect(f"{login_url}?next={quote(request.get_full_path())}")

            has_access = (
                request.user.is_staff
                or getattr(request.user, 'is_superuser', False)
                or request.user.has_event_permission(event.organizer, event, request=request)
                or request.user.has_organizer_permission(event.organizer, request=request)
            )
            if not has_access:
                raise PermissionDenied(_("You do not have permission to access the video organizer area."))

        index_path = VIDEO_DIST_DIR / 'index.html'
        if settings.VITE_DEV_MODE:
            html_content = fetch_vite_html(VIDEO_DEV_SERVER)
        elif index_path.is_file():
            html_content = index_path.read_text()
        else:
            html_content = '<!-- /video build missing: {} -->'.format(index_path)

        base_href = '/video/'
        if event:
            api_base = f'/api/v1/events/{event.slug}/'

            cfg = event.config or {}

            with scope(event=event):
                requested_version = request.GET.get('v') or request.GET.get('version')
                schedule = None
                if requested_version:
                    schedule = (
                        event.schedules.filter(version=requested_version)
                        .order_by('-published')
                        .first()
                    )
                if not schedule:
                    schedule = event.current_schedule

                schedule_version = schedule.version if schedule else None
                schedule_exporters = build_public_schedule_exporters(event, version=schedule_version)

            if self.is_organizer:
                base_path = f'/video/event/{event.organizer.slug}/{event.slug}'
                base_href = f'/video/event/{event.organizer.slug}/{event.slug}/'
            else:
                base_path = event.urls.video_base.rstrip('/')
                base_href = event.urls.video_base

            has_ticket_access = bool(
                request.user.is_authenticated
                and (
                    request.user.is_staff
                    or getattr(request.user, 'is_superuser', False)
                    or request.user.has_event_permission(event.organizer, event, 'can_view_orders', request=request)
                    or request.user.has_event_permission(event.organizer, event, 'can_change_items', request=request)
                    or request.user.has_event_permission(event.organizer, event, 'can_change_event_settings', request=request)
                )
            )
            has_talk_access = bool(
                request.user.is_authenticated
                and (
                    request.user.is_staff
                    or getattr(request.user, 'is_superuser', False)
                    or request.user.has_event_permission(event.organizer, event, 'can_change_submissions', request=request)
                )
            )
            can_manage = bool(
                request.user.is_authenticated
                and (
                    request.user.is_staff
                    or getattr(request.user, 'is_superuser', False)
                    or request.user.has_event_permission(event.organizer, event, request=request)
                    or request.user.has_organizer_permission(event.organizer, request=request)
                )
            )

            injected = {
                'isOrganizerArea': self.is_organizer,
                'hasOrganiserPermissions': can_manage,
                'publicVideoUrl': f'/{event.organizer.slug}/{event.slug}/video',
                'homeUrl': safe_reverse('eventyay_common:event.index', organizer=event.organizer.slug, event=event.slug),
                'ticketUrl': safe_reverse('control:event.index', organizer=event.organizer.slug, event=event.slug) if has_ticket_access else None,
                'talkUrl': safe_reverse('orga:event.dashboard', organizer=event.organizer.slug, event=event.slug) if has_talk_access else None,
                'videoUrl': f'/video/event/{event.organizer.slug}/{event.slug}/',
                'commonAccountUrl': safe_reverse('eventyay_common:event.index', organizer=event.organizer.slug, event=event.slug),
                'api': {
                    'base': api_base,
                    'socket': '{}://{}/ws/event/{}/'.format(
                        'wss' if request.is_secure() else 'ws',
                        request.get_host(),
                        event.pk,
                    ),
                    'upload': safe_reverse('storage:upload', event_id=event.pk) or '',
                    'uploadMaxSize': settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_OTHER],
                    'scheduleImport': safe_reverse('storage:schedule_import', event_id=event.pk) or '',
                    'systemlog': safe_reverse('live:systemlog') or '',
                },
                'features': getattr(event, 'feature_flags', {}) or {},
                'liveFeatures': {
                    'chat_rooms': False,
                    'kiosks': False,
                    'direct_messaging': False,
                    'announcements': False,
                    **(cfg.get('live_features') or {}),
                },
                'externalAuthUrl': getattr(event, 'external_auth_url', None),
                'locale': event.locale,
                'date_locale': cfg.get('date_locale', 'en-ie'),
                'theme': build_video_theme_for_event(event),
                'video_player': cfg.get('video_player', {}),
                'mux': cfg.get('mux', {}),
                'schedule': None,
                'scheduleMeta': {
                    'version': schedule_version or '',
                    'is_current': schedule == event.current_schedule if schedule else False,
                    'changelog_url': str(event.urls.changelog),
                    'current_schedule_url': f'{base_href}schedule' if event.current_schedule else '',
                    'versions': [
                        {
                            'version': v,
                            'url': f'{base_href}schedule?v={v}',
                            'isCurrent': v == schedule_version,
                        }
                        for v in event.schedules.filter(version__isnull=False)
                        .order_by('-published')
                        .values_list('version', flat=True)
                    ],
                    'exporters': schedule_exporters,
                },
                # Extra values expected by config.js/theme
                'eventUrl': str(event.urls.base),
                'showPublicly': bool(request.user.is_authenticated and request.user.show_publicly),
                'isStaff': bool(request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)),
                'hasStaffSession': check_has_active_staff_session(request.user, request.session.session_key),
                'eventSlug': event.slug,
                'organizerSlug': event.organizer.slug if event.organizer else None,
                'eventDates': {
                    'date_from': event.date_from.isoformat() if event.date_from else None,
                    'date_to': event.date_to.isoformat() if event.date_to else None,
                },
                'eventTimezone': event.settings.timezone,
                'eventTitle': str(event.name),
                'visibleLogoUrl': event.visible_logo_url or '',
                'visibleHeaderImageUrl': event.visible_header_image_url or '',
                'showDateTo': bool(event.settings.show_date_to),
                'showTimes': bool(event.settings.show_times),
                'basePath': base_path,
                'defaultLocale': 'en',
                'locales': get_ui_language_options(),
                'noThemeEndpoint': True,  # Prevent frontend from requesting missing /theme endpoint
                'translationMessages': {
                    'favs_anonymous_notice': str(_(
                        'Your favourites can only be saved locally in this browser. '
                        'Please sign in or register to sync starred sessions and use more features. '
                        'Locally saved stars may be lost if you clear your browser data; '
                        'we are not responsible for data loss in this case.'
                    )),
                    'favs_not_saved': str(_(
                        'Could not save favourites in this browser. Please check your browser storage settings.'
                    )),
                    'no_matching_options': str(_('Sorry, no matching options.')),
                    'view_changelog': str(_('View Changelog')),
                    'go_to_current_version': str(_('Go to current version')),
                    'reset_all_filters': str(_('Reset all filters')),
                    'sort_by': str(_('Sort')),
                    'sort_by_room': str(_('By room')),
                    'sort_by_title': str(_('A\u2013Z')),
                    'sort_by_popularity': str(_('Most popular')),
                    'fullscreen': str(_('Fullscreen')),
                    'exit_fullscreen': str(_('Exit Fullscreen')),
                    'latest': str(_('Latest')),
                    'version_warning_editable': str(_(
                        'You are currently viewing the editable schedule version.'
                        ' It may not match the released version.'
                    )),
                    'version_warning_old': str(_('You are currently viewing an older schedule version.')),
                    'join_room': str(_('Join room')),
                    'join_session': str(_('Join session')),
                    'view_video': str(_('View Video')),
                    'watch_live': str(_('Watch live')),
                    'speaker_fallback': str(pgettext('noun', 'Speaker')),
                    'speaker_name_not_provided': str(_('Speaker name not provided')),
                    'add_to_calendar': str(_('Add to Calendar')),
                    'ical': str(_('iCal')),
                    'json': str(_('JSON')),
                    'xml': str(_('XML')),
                    'xcal': str(_('XCal')),
                    'google_calendar': str(_('Google Calendar')),
                    'webcal': str(_('Webcal')),
                    'yes': str(_('Yes')),
                    'no': str(_('No')),
                    'no_speakers_found': str(_('No speakers found.')),
                    'sessions': str(_('Sessions')),
                    'tracks': str(_('Tracks')),
                    'speakers': str(_('Speakers')),
                    'downloads': str(_('Downloads')),
                    'starred_by': str(_('Starred by')),
                    'starred': str(_('Starred')),
                    'show_talk_starrers': str(_('Share starred sessions')),
                    'show_talk_starrers_tooltip': str(_(
                        'Make your starred sessions visible to others. You can open someone else\'s starred list only if they have enabled sharing.'
                    )),
                    'export': str(_('Export')),
                    'exports': str(_('Exports')),
                    'no_file_provided': str(_('No file provided')),
                    'no_response': str(_('No response')),
                    'other_timezones': str(_('Other Timezones')),
                    'current': str(_('current')),
                    'print': str(_('Print')),
                    'list_view': str(_('List View')),
                    'calendar_view': str(_('Calendar View')),
                    'search': str(_('Search')),
                    'featured_speakers': str(_('Featured Speakers')),
                    'view_profile': str(_('View speaker profile')),
                    'no_starred_sessions': str(_('No starred sessions.')),
                    'no_schedule_available': str(_('No schedule has been published yet. Please check back later.')),
                },
            }

            class EventyayJSONEncoder(DjangoJSONEncoder):
                def default(self, obj):
                    if isinstance(obj, (Promise, LazyI18nString)):
                        return force_str(obj)
                    return super().default(obj)

            extra_script = f'<script>window.eventyay={json.dumps(injected, cls=EventyayJSONEncoder)}</script>'
            # Inject extra_script before the first <script ...> occurrence (handles attributes like type/src)
            lower_html = html_content.lower()
            before, sep, _rest = lower_html.partition('<script ')
            if sep:
                idx = len(before)
                html_content = f'{html_content[:idx]}{extra_script}{html_content[idx:]}'
            else:
                html_content = f'{extra_script}{html_content}'

        elif event_identifier:
            # Event identifier provided but not found -> 404
            return HttpResponse('Event not found', status=404)

        if not settings.VITE_DEV_MODE and '<base ' not in html_content.lower():
            # Ensure assets resolve correctly regardless of nested route
            html_content = html_content.replace('<head>', f'<head><base href="{base_href}">', 1)

        resp = HttpResponse(html_content, content_type='text/html')
        resp._csp_ignore = True  # Disable CSP for SPA (relies on dynamic inline scripts)
        return resp


class VideoAssetView(View):
    def get(self, request, path='', *args, **kwargs):
        if settings.VITE_DEV_MODE:
            try:
                with urlopen(f'{VIDEO_DEV_SERVER}/{path}', timeout=5) as resp:
                    content = resp.read()
                    ctype = resp.headers.get('Content-Type', guess_type(path)[0] or 'application/octet-stream')
                    r = HttpResponse(content, content_type=ctype)
                    r._csp_ignore = True
                    return r
            except OSError:
                logger.warning('Video asset not found via Vite dev server: %s', path)
                raise Http404()
        # Accept empty path -> index handling done by SPA view
        candidate_paths = (
            [
                os.path.join(VIDEO_DIST_DIR, path),
                os.path.join(VIDEO_DIST_DIR, 'assets', path),
            ]
            if path
            else []
        )
        for fp in candidate_paths:
            if os.path.isfile(fp):
                rel = os.path.relpath(fp, VIDEO_DIST_DIR)
                resp = static_serve(request, rel, document_root=VIDEO_DIST_DIR)
                resp._csp_ignore = True
                # Ensure proper content type for module scripts
                ctype, _rest = guess_type(fp)
                if ctype:
                    resp['Content-Type'] = ctype
                return resp
        logger.warning('Video asset not found: %s', path)
        raise Http404()

class AnonymousInviteRedirectView(View):
    """
    Handle anonymous room invite short tokens (e.g., /eGHhXr/).
    Redirects to the video SPA standalone anonymous room view:
    /{organizer}/{event}/video/standalone/{room_id}/anonymous#invite={token}
    """
    def get(self, request, token, *args, **kwargs):
        try:
            invite = AnonymousInvite.objects.select_related(
                'event', 'event__organizer', 'room'
            ).get(
                short_token=token,
                expires__gte=now(),
            )
        except AnonymousInvite.DoesNotExist:
            raise Http404("Invalid or expired anonymous room link")

        # Build redirect URL to the video SPA standalone anonymous view
        event = invite.event
        organizer_slug = event.organizer.slug
        event_slug = event.slug
        room_id = invite.room_id

        # Redirect to /{organizer}/{event}/video/standalone/{room_id}/anonymous#invite={token}
        redirect_url = f"/{organizer_slug}/{event_slug}/video/standalone/{room_id}/anonymous#invite={token}"
        return redirect(redirect_url)


class VideoAdminRedirectView(View):
    """
    Redirects legacy /<organizer>/<event>/video/admin/* or /<organizer>/<event>/video/event/* routes
    to the new organizer area: /video/event/<organizer>/<event>/*
    """
    def get(self, request, organizer, event, subpath=None, *args, **kwargs):
        target = f'/video/event/{organizer}/{event}/'
        if subpath:
            target = f"{target.rstrip('/')}/{subpath.lstrip('/')}"
        query = request.META.get('QUERY_STRING')
        if query:
            target = f"{target}?{query}"
        return redirect(target)


