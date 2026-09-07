from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView
from django_scopes import scopes_disabled
from eventyay.common.views.mixins import PaginationMixin
from i18nfield.strings import LazyI18nString

from eventyay.base.models import Event, Organizer, OrganizerFollower
from eventyay.base.models.page import Page
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.permissions import is_admin_mode_active
from eventyay.eventyay_common.navigation import get_global_navigation
from eventyay.multidomain.urlreverse import eventreverse

_SEARCH_PAGE_LIMIT = 200


def _event_search_qs(query):
    return (
        Event.objects.select_related('organizer')
        .prefetch_related('_settings_objects')
        .filter(live=True, is_public=True, testmode=False)
        .filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(organizer__name__icontains=query)
            | Q(location__icontains=query)
        )
        .order_by('date_from')
    )


def _search_events(query, limit=10):
    with scopes_disabled():
        results = []
        for event in _event_search_qs(query)[:limit]:
            if event.has_component_testmode:
                continue
            url = eventreverse(event, 'presale:event.index')
            results.append({
                'name': str(event.name),
                'url': url,
                'date': event.get_date_range_display(),
                'image': event.preview_image_url_with_fallback or '',
            })
    return results


class StartPageView(TemplateView):
    template_name = 'pretixpresale/startpage.html'

    def get(self, request, *args, **kwargs):
        if request.GET.get('format') == 'json':
            query = request.GET.get('q', '').strip()
            if not query:
                return JsonResponse({'results': []})
            return JsonResponse({'results': _search_events(query)})
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_common_base_context(self.request))
        search_query = self.request.GET.get('q', '').strip()
        ctx['search_query'] = search_query
        with scopes_disabled():
            if search_query:
                qs = _event_search_qs(search_query)[:_SEARCH_PAGE_LIMIT]
                ctx['events'] = [e for e in qs if not e.has_component_testmode]
                return ctx

            today_datetime = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
            base_qs = (
                Event.objects.select_related('organizer')
                .prefetch_related('_settings_objects')
                .filter(live=True, testmode=False)
                .exclude(_settings_objects__key='talks_testmode', _settings_objects__value='True')
            )
            future_filter = Q(date_to__gte=today_datetime) | Q(date_to__isnull=True, date_from__gte=today_datetime)
            past_filter = Q(date_to__lt=today_datetime) | Q(date_to__isnull=True, date_from__lt=today_datetime)

            featured_qs = base_qs.filter(startpage_featured=True).filter(future_filter).order_by('date_from')[:8]
            upcoming_qs = (
                base_qs.filter(startpage_visible=True, startpage_featured=False)
                .filter(future_filter)
                .order_by('date_from')[:8]
            )
            past_qs = (
                base_qs.filter(startpage_visible=True)
                .filter(past_filter)
                .order_by('-date_from')[:8]
            )

            ctx['featured_events'] = list(featured_qs)
            ctx['upcoming_events'] = list(upcoming_qs)
            ctx['past_events'] = list(past_qs)

            followed_upcoming_events = []
            if self.request.user.is_authenticated:
                followed_org_ids = OrganizerFollower.objects.filter(
                    user=self.request.user
                ).values_list('organizer_id', flat=True)
                followed_qs = (
                    base_qs.filter(
                        organizer_id__in=followed_org_ids,
                    )
                    .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
                    .filter(future_filter)
                    .order_by('date_from')[:8]
                )
                followed_upcoming_events = list(followed_qs)

            ctx['followed_upcoming_events'] = followed_upcoming_events
        return ctx


def _common_base_context(request):
    """Return shared context variables for the three dedicated event-list views."""
    ctx = {
        'site_name': settings.INSTANCE_NAME,
        'staff_session': is_admin_mode_active(request),
    }
    ctx['nav_items'] = get_global_navigation(request) if request.user.is_authenticated else []
    ctx['show_link_in_header_for_start_page'] = Page.objects.filter(
        link_on_website_start_page=True,
        link_in_header=True,
    )
    ctx['show_link_in_footer_for_start_page'] = Page.objects.filter(
        link_on_website_start_page=True,
        link_in_footer=True,
    )

    settings_obj = GlobalSettingsObject().settings
    ctx['global_settings'] = settings_obj
    header_image = settings_obj.get('startpage_header_image', as_type=str, default='')
    if header_image.startswith('file://'):
        header_image = header_image[7:]
    elif header_image.startswith('public:'):
        header_image = header_image[7:]
    ctx['startpage_header_image_url'] = default_storage.url(header_image) if header_image else ''
    header_text = settings_obj.get(
        'startpage_header_text',
        as_type=LazyI18nString,
        default='',
    )
    ctx['startpage_header_text'] = header_text or settings.INSTANCE_NAME
    return ctx


@method_decorator(scopes_disabled(), name='dispatch')
class UpcomingEventsView(PaginationMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'pretixpresale/events/upcoming.html'
    paginate_by = 20

    def get_queryset(self):
        today_datetime = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = (
            Event.objects.select_related('organizer')
            .prefetch_related('_settings_objects')
            .filter(live=True, is_public=True)
            .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
            .filter(Q(date_to__gte=today_datetime) | Q(date_to__isnull=True, date_from__gte=today_datetime))
            .filter(testmode=False)
            .exclude(_settings_objects__key='talks_testmode', _settings_objects__value='True')
            .order_by('date_from')
        )
        if self.request.GET.get('cfp') == 'open':
            qs = qs.filter(Q(cfp__deadline__isnull=True) | Q(cfp__deadline__gte=timezone.now()))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pagination_sizes'] = [20, 50, 100]
        ctx['cfp_open_filter'] = self.request.GET.get('cfp') == 'open'
        ctx.update(_common_base_context(self.request))
        return ctx


@method_decorator(scopes_disabled(), name='dispatch')
class PastEventsView(PaginationMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'pretixpresale/events/past.html'
    paginate_by = 20

    def get_queryset(self):
        today_datetime = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = (
            Event.objects.select_related('organizer')
            .prefetch_related('_settings_objects')
            .filter(live=True)
            .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
            .filter(Q(date_to__lt=today_datetime) | Q(date_to__isnull=True, date_from__lt=today_datetime))
            .filter(testmode=False)
            .exclude(_settings_objects__key='talks_testmode', _settings_objects__value='True')
            .order_by('-date_from')
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pagination_sizes'] = [20, 50, 100]
        ctx.update(_common_base_context(self.request))
        return ctx


@method_decorator(login_required(login_url='auth.login'), name='dispatch')
@method_decorator(scopes_disabled(), name='dispatch')
class FollowedEventsView(TemplateView):
    template_name = 'pretixpresale/events/followed.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_common_base_context(self.request))
        today_datetime = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)

        followed_org_ids = OrganizerFollower.objects.filter(
            user=self.request.user
        ).values_list('organizer_id', flat=True)

        organizers = Organizer.objects.filter(id__in=followed_org_ids)

        organizer_groups = []
        for org in organizers:
            events_qs = (
                Event.objects.filter(
                    organizer=org,
                    live=True,
                )
                .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
                .filter(Q(date_to__gte=today_datetime) | Q(date_to__isnull=True, date_from__gte=today_datetime))
                .filter(testmode=False)
                .exclude(_settings_objects__key='talks_testmode', _settings_objects__value='True')
                .select_related('organizer')
                .prefetch_related('_settings_objects')
                .order_by('date_from')[:9]
            )
            org_events = list(events_qs)
            if org_events:
                organizer_groups.append({
                    'organizer': org,
                    'events': org_events
                })

        ctx['organizer_groups'] = organizer_groups
        return ctx
