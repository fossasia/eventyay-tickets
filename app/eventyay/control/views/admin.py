import json
import logging
import sys
from datetime import UTC, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers import registry
from cron_descriptor import Options, get_description
from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    F,
    Min,
    Prefetch,
    Q,
    Sum,
    When,
)
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.timezone import is_aware, localtime, make_aware, now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_celery_beat.models import PeriodicTask, PeriodicTasks
from django_context_decorator import context
from django_scopes import scopes_disabled
from django.core.cache import cache
from django.apps import apps

from redis.exceptions import RedisError

from eventyay import __version__
from eventyay.celery_app import app
from eventyay.control.forms.filter import AttendeeFilterForm
from eventyay.control.forms.admin.admin import UpdateSettingsForm

from eventyay.api.models import OAuthAccessToken, OAuthApplication, WebHook, WebHookCall
from eventyay.base.models.auth import User
from eventyay.base.models.checkin import Checkin
from eventyay.base.models.event import Event, Event_SettingsStore
from eventyay.base.models.orders import Order, OrderPosition, OrderPayment, OrderRefund
from eventyay.base.models.devices import Device
from eventyay.base.models.mail import QueuedMail
from eventyay.base.models.organizer import Organizer, TeamAPIToken
from eventyay.base.models.settings import GlobalSettings
from eventyay.base.models.cfp import CfP
from eventyay.base.models.submission import Submission, SubmissionStates
from eventyay.base.models.vouchers import InvoiceVoucher, generate_code
from eventyay.base.models.product import Product
from eventyay.base.services.update_check import check_result_table, update_check
from eventyay.common.text.phrases import phrases
from eventyay.control.forms.admin.vouchers import InvoiceVoucherForm, VoucherFilterForm
from eventyay.control.forms.filter import AdminOrderFilterForm, OrganizerFilterForm, SubmissionFilterForm, TaskFilterForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.video.admin_dashboard import get_video_server_dashboard_rows
from eventyay.control.views import PaginationMixin
from eventyay.control.views.main import EventList

logger = logging.getLogger(__name__)


class AdminDashboard(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/dashboard.html'

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'refresh' or 'refresh' in request.POST:
            cache.delete_many([
                'admin_dashboard_events_pending_setup',
                'admin_dashboard_orders_top5',
                'admin_dashboard_email_stats',
                'admin_dashboard_celery_depth',
                'admin_dashboard_sso_stats',
                'admin_dashboard_api_stats',
            ])
            messages.success(request, _('Dashboard cache refreshed successfully.'))
        return redirect('eventyay_admin:admin.dashboard')

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        n = now()
        email_stats = None

        # User KPIs
        user_stats = User.objects.aggregate(
            total=Count('id'),
            new_24h=Count('id', filter=Q(date_joined__gte=n - timedelta(hours=24))),
            new_7d=Count('id', filter=Q(date_joined__gte=n - timedelta(days=7))),
            new_30d=Count('id', filter=Q(date_joined__gte=n - timedelta(days=30))),
            banned=Count('id', filter=Q(moderation_state=User.ModerationState.BANNED)),
            is_spam=Count('id', filter=Q(is_spam=True)),
            recently_active=Count('id', filter=Q(last_login__gte=n - timedelta(days=30), last_login__isnull=False)),
            deleted=Count('id', filter=Q(deleted=True) | Q(email__endswith='@disabled.eventyay.com')),
            staff=Count('id', filter=Q(is_staff=True) | Q(is_administrator=True)),
        )
        users_verified = EmailAddress.objects.filter(verified=True, primary=True).values('user_id').distinct().count()

        ctx['users_total'] = user_stats['total']
        ctx['users_verified'] = users_verified
        ctx['users_unverified'] = user_stats['total'] - users_verified
        ctx['users_new_24h'] = user_stats['new_24h']
        ctx['users_new_7d'] = user_stats['new_7d']
        ctx['users_new_30d'] = user_stats['new_30d']
        ctx['users_banned'] = user_stats['banned']
        ctx['users_is_spam'] = user_stats['is_spam']
        ctx['users_staff'] = user_stats['staff']
        ctx['users_recently_active'] = user_stats['recently_active']
        ctx['users_deleted'] = user_stats['deleted']

        # Organizer KPIs
        ctx['organizers_total'] = Organizer.objects.count()

        with scopes_disabled():
            # Event KPIs
            event_kpis = Event.objects.aggregate(
                total=Count('id'),
                live=Count('id', filter=Q(live=True)),
                series=Count('id', filter=Q(has_subevents=True)),
                featured=Count('id', filter=Q(startpage_featured=True)),
            )
            ctx['events_total'] = event_kpis['total']
            ctx['events_live'] = event_kpis['live']
            ctx['events_draft'] = event_kpis['total'] - event_kpis['live']
            ctx['events_past'] = (
                Event.objects.filter(has_subevents=False)
                .filter(
                    Q(Q(date_to__isnull=True) & Q(date_from__lt=n))
                    | Q(Q(date_to__isnull=False) & Q(date_to__lt=n))
                )
                .count()
            )
            ctx['events_series'] = event_kpis['series']
            ctx['events_featured'] = event_kpis['featured']
            ctx['events_meetup'] = (
                Event_SettingsStore.objects.filter(
                    key='event_type',
                    value__in=['"meetup"', 'meetup'],
                )
                .values('object_id')
                .distinct()
                .count()
            )

            # Event activity
            ctx['events_running'] = (
                Event.objects.filter(has_subevents=False, live=True, date_from__lte=n)
                .filter(Q(date_to__isnull=True) | Q(date_to__gte=n))
                .count()
            )
            ctx['events_upcoming'] = list(
                Event.objects.filter(has_subevents=False, date_from__gt=n)
                .select_related('organizer')
                .order_by('date_from')[:10]
            )
            ctx['events_recent'] = list(
                Event.objects.filter(has_subevents=False)
                .select_related('organizer')
                .order_by('-pk')[:10]
            )

            def _get_events_pending_setup():
                events_with_payment = Event_SettingsStore.objects.filter(
                    key__startswith='payment_',
                    key__endswith='__enabled',
                    value='True',
                ).exclude(
                    key__in=[
                        'payment_free__enabled',
                        'payment_boxoffice__enabled',
                        'payment_offsetting__enabled',
                        'payment_giftcard__enabled',
                    ]
                ).values_list('object_id', flat=True)

                events_with_paid_products = Product.objects.filter(
                    default_price__gt=0
                ).values_list('event_id', flat=True)

                events_no_products = Event.objects.filter(products__isnull=True)
                events_missing_payment = Event.objects.filter(id__in=events_with_paid_products).exclude(
                    id__in=events_with_payment
                )

                events_pending_setup = (events_no_products | events_missing_payment).distinct()

                candidates = list(
                    events_pending_setup.select_related('organizer')
                    .prefetch_related('products')
                    .order_by('-pk')[:20]
                )

                candidate_ids = [str(c.pk) for c in candidates]
                payment_enabled_event_ids = set(
                    Event_SettingsStore.objects.filter(
                        object_id__in=candidate_ids,
                        key__startswith='payment_',
                        key__endswith='__enabled',
                        value='True',
                    ).exclude(
                        key__in=[
                            'payment_free__enabled',
                            'payment_boxoffice__enabled',
                            'payment_offsetting__enabled',
                            'payment_giftcard__enabled',
                        ]
                    ).values_list('object_id', flat=True)
                )
                res = []
                for event in candidates:
                    products = list(event.products.all())
                    has_products = bool(products)
                    has_paid_products = any(p.default_price > 0 for p in products)
                    has_payment_provider = str(event.pk) in payment_enabled_event_ids
                    if not has_products or (has_paid_products and not has_payment_provider):
                        event.has_products = has_products
                        res.append(event)
                        if len(res) == 5:
                            break
                return res

            ctx['events_pending_setup_list'] = cache.get_or_set(
                'admin_dashboard_events_pending_setup',
                _get_events_pending_setup,
                300
            )

            # CfP stats
            ctx['events_cfp_open_count'] = CfP.objects.filter(
                Q(deadline__isnull=True) | Q(deadline__gte=n) | Q(event__submission_types__deadline__gte=n)
            ).distinct().count()

            # Order KPIs
            ctx['orders_total'] = Order.objects.count()

            # Gross Revenue from confirmed payments
            payment_sums = {
                r['order__event__currency']: r['total']
                for r in OrderPayment.objects.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED)
                .values('order__event__currency')
                .annotate(total=Sum('amount'))
                .order_by()
            }

            refund_sums = {
                r['order__event__currency']: r['total']
                for r in OrderRefund.objects.filter(state=OrderRefund.REFUND_STATE_DONE)
                .values('order__event__currency')
                .annotate(total=Sum('amount'))
                .order_by()
            }
            # Order counts per currency
            currency_counts = Order.objects.values('event__currency').annotate(
                paid=Count('pk', filter=Q(status=Order.STATUS_PAID) & ~Q(total=0), distinct=True),
                pending=Count('pk', filter=Q(status=Order.STATUS_PENDING), distinct=True),
                cancelled=Count('pk', filter=Q(status=Order.STATUS_CANCELED), distinct=True),
                free=Count('pk', filter=Q(status=Order.STATUS_PAID) & Q(total=0), distinct=True)
            ).order_by()
            order_counts_by_currency = {
                entry['event__currency']: {
                    'paid': entry['paid'],
                    'pending': entry['pending'],
                    'cancelled': entry['cancelled'],
                    'free': entry['free']
                }
                for entry in currency_counts
            }

            all_currencies = sorted(list(
                set(payment_sums.keys()) | set(refund_sums.keys()) | set(order_counts_by_currency.keys())
            ))

            ctx['orders_net_revenue'] = []
            for currency in all_currencies:
                gross = payment_sums.get(currency, Decimal('0.00')) or Decimal('0.00')
                refunded = refund_sums.get(currency, Decimal('0.00')) or Decimal('0.00')
                net = gross - refunded
                counts = order_counts_by_currency.get(currency, {})
                ctx['orders_net_revenue'].append({
                    'currency': currency,
                    'gross': gross,
                    'refunded': refunded,
                    'net': net,
                    'paid_count': counts.get('paid', 0),
                    'pending_count': counts.get('pending', 0),
                    'cancelled_count': counts.get('cancelled', 0),
                    'free_count': counts.get('free', 0),
                })

            ctx['orders_revenue'] = sorted(
                [
                    {'event__currency': item['currency'], 'total': item['net']}
                    for item in ctx['orders_net_revenue']
                ],
                key=lambda x: x['total'],
                reverse=True
            )

            # Schedule stats
            ctx['events_with_schedule_count'] = (
                Event.objects.filter(schedules__published__isnull=False).distinct().count()
            )

            # Programme KPIs
            submission_kpis = Submission.objects.aggregate(
                total=Count('id'),
                submitted=Count('id', filter=Q(state=SubmissionStates.SUBMITTED)),
                total_submitted=Count(
                    'id',
                    filter=~Q(state__in=[SubmissionStates.DRAFT, SubmissionStates.DELETED]),
                ),
                accepted=Count('id', filter=Q(state=SubmissionStates.ACCEPTED)),
                rejected=Count('id', filter=Q(state=SubmissionStates.REJECTED)),
                confirmed=Count('id', filter=Q(state=SubmissionStates.CONFIRMED)),
            )
            ctx['sessions_total'] = submission_kpis['total']
            ctx['sessions_submitted'] = submission_kpis['submitted']
            ctx['sessions_total_submitted'] = submission_kpis['total_submitted']
            ctx['sessions_accepted'] = submission_kpis['accepted']
            ctx['sessions_rejected'] = submission_kpis['rejected']
            ctx['sessions_confirmed'] = submission_kpis['confirmed']

            ctx['sessions_recent_submissions'] = list(
                Submission.objects.filter(state=SubmissionStates.SUBMITTED)
                .select_related('event', 'event__organizer')
                .order_by('-pk')[:8]
            )

            speaker_kpis = Submission.speakers.through.objects.aggregate(
                total=Count(
                    'user_id',
                    distinct=True,
                    filter=~Q(submission__state__in=[SubmissionStates.DRAFT, SubmissionStates.DELETED]),
                ),
                confirmed=Count(
                    'user_id',
                    distinct=True,
                    filter=Q(submission__state=SubmissionStates.CONFIRMED),
                ),
                unconfirmed=Count(
                    'user_id',
                    distinct=True,
                    filter=~Q(submission__state__in=[
                        SubmissionStates.CONFIRMED,
                        SubmissionStates.REJECTED,
                        SubmissionStates.CANCELED,
                        SubmissionStates.WITHDRAWN,
                        SubmissionStates.DELETED,
                        SubmissionStates.DRAFT,
                    ]),
                ),
            )
            ctx['speakers_total'] = speaker_kpis['total']
            ctx['speakers_confirmed'] = speaker_kpis['confirmed']
            ctx['speakers_unconfirmed'] = speaker_kpis['unconfirmed']

            # Attendee / ticket KPIs
            attendee_stats = OrderPosition.objects.filter(
                order__status=Order.STATUS_PAID
            ).aggregate(
                attendees_total=Count('id', filter=Q(addon_to__isnull=True)),
                tickets_issued=Count('id')
            )
            ctx['attendees_total'] = attendee_stats['attendees_total']
            ctx['tickets_issued'] = attendee_stats['tickets_issued']

            # Orders Detail
            try:
                ctx['orders_recent_10'] = list(
                    Order.objects.order_by('-datetime')
                    .select_related('event', 'event__organizer')[:10]
                )

                # Cache the heavy Top aggregates to prevent production database performance hits
                def _get_orders_top5():
                    top5_event = list(
                        Order.objects.filter(status=Order.STATUS_PAID)
                        .values('event__name', 'event__slug')
                        .annotate(count=Count('pk'))
                        .order_by('-count')[:5]
                    )
                    top5_provider = list(
                        OrderPayment.objects.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED)
                        .values('provider')
                        .annotate(count=Count('order_id', distinct=True))
                        .order_by('-count')[:5]
                    )
                    return {'event': top5_event, 'provider': top5_provider}

                top5_stats = cache.get_or_set('admin_dashboard_orders_top5', _get_orders_top5, 300)
                ctx['orders_top5_by_event'] = top5_stats['event']
                ctx['orders_top5_by_provider'] = top5_stats['provider']
                ctx['orders_detail_unavailable'] = False
            except (DatabaseError, RedisError):
                logger.exception('AdminDashboard: failed to load orders detail section')
                ctx['orders_detail_unavailable'] = True

            # Email Status
            try:
                email_stats = cache.get_or_set(
                    'admin_dashboard_email_stats',
                    lambda: QueuedMail.objects.aggregate(
                        sent_24h=Count('id', filter=Q(sent__isnull=False, sent__gte=n - timedelta(hours=24))),
                        sent_7d=Count('id', filter=Q(sent__isnull=False, sent__gte=n - timedelta(days=7))),
                        unsent=Count('id', filter=Q(sent__isnull=True)),
                    ),
                    300
                )
                ctx['email_sent_today'] = email_stats['sent_24h']
                ctx['email_sent_week'] = email_stats['sent_7d']
                ctx['email_unsent_count'] = email_stats['unsent']
                ctx['email_smtp_warning'] = (
                    not getattr(settings, 'EMAIL_HOST', None)
                    or getattr(settings, 'EMAIL_BACKEND', '') == 'django.core.mail.backends.dummy.EmailBackend'
                )
                ctx['email_status_unavailable'] = False
            except (DatabaseError, RedisError):
                logger.exception('AdminDashboard: failed to load email status section')
                ctx['email_status_unavailable'] = True

            # Platform Health
            try:
                celery_enabled = getattr(settings, 'HAS_CELERY', False)
                celery_depth = None
                celery_depth_unavailable = False
                if celery_enabled:
                    try:
                        def _get_depth():
                            inspector = app.control.inspect(timeout=1)
                            active = inspector.active() or {}
                            return sum(len(v) for v in active.values())
                        celery_depth = cache.get_or_set('admin_dashboard_celery_depth', _get_depth, 300)
                    except (RedisError, TimeoutError, ConnectionError, OSError):
                        logger.exception('AdminDashboard: failed to get Celery queue depth')
                        celery_depth_unavailable = True

                periodic_tasks = list(
                    PeriodicTask.objects.filter(enabled=True)
                    .order_by('name')[:20]
                )
                local_timezone = ZoneInfo(settings.TIME_ZONE)
                for task in periodic_tasks:
                    if task.last_run_at is None:
                        task.formatted_last_run_at = '-'
                    else:
                        task.formatted_last_run_at = date_format(
                            localtime(task.last_run_at, local_timezone), format='M. d, Y, g:i a'
                        )
                    task.display_name = task.name.replace('_', ' ').capitalize()

                scheduled_tasks_run_24h = PeriodicTask.objects.filter(
                    last_run_at__gte=n - timedelta(hours=24)
                ).count()
                payments_failed_24h = OrderPayment.objects.filter(
                    state=OrderPayment.PAYMENT_STATE_FAILED,
                    created__gte=n - timedelta(hours=24)
                ).count()
                refunds_pending_count = OrderRefund.objects.filter(
                    state__in=[OrderRefund.REFUND_STATE_CREATED, OrderRefund.REFUND_STATE_TRANSIT]
                ).count()
                active_devices_count = Device.objects.filter(
                    initialized__isnull=False,
                    revoked=False
                ).count()

                ctx['celery_depth'] = celery_depth
                ctx['celery_depth_unavailable'] = celery_depth_unavailable
                ctx['celery_enabled'] = celery_enabled
                ctx['periodic_tasks'] = periodic_tasks
                ctx['scheduled_tasks_run_24h'] = scheduled_tasks_run_24h
                ctx['payments_failed_24h'] = payments_failed_24h
                ctx['refunds_pending_count'] = refunds_pending_count
                ctx['active_devices_count'] = active_devices_count
                ctx['platform_health_unavailable'] = False
            except (DatabaseError, RedisError):
                logger.exception('AdminDashboard: failed to load platform health section')
                ctx['platform_health_unavailable'] = True

            # SSO and Authentication
            try:
                if apps.is_installed('allauth.socialaccount'):
                    ctx['sso_section_enabled'] = True

                    def _get_sso():
                        db_counts = {
                            item['provider']: item['count']
                            for item in SocialAccount.objects.values('provider').annotate(count=Count('id'))
                        }

                        providers_list = []
                        registered_ids = set()
                        default_providers = {
                            'google': 'Google',
                            'github': 'GitHub',
                            'mediawiki': 'MediaWiki',
                        }
                        for p_id, p_name in default_providers.items():
                            registered_ids.add(p_id)
                            providers_list.append({
                                'provider': p_id,
                                'name': p_name,
                                'count': db_counts.get(p_id, 0)
                            })

                        try:
                            for provider in registry.get_list():
                                p_id = provider.id
                                p_name = provider.name
                                if p_id not in registered_ids:
                                    registered_ids.add(p_id)
                                    providers_list.append({
                                        'provider': p_id,
                                        'name': p_name,
                                        'count': db_counts.get(p_id, 0)
                                    })
                        except (AttributeError, KeyError, ImportError):
                            pass

                        for p_id, count in db_counts.items():
                            if p_id not in registered_ids:
                                providers_list.append({
                                    'provider': p_id,
                                    'name': p_id.capitalize(),
                                    'count': count
                                })
                        providers_list.sort(key=lambda x: (-x['count'], x['name']))

                        multi_conn = (
                            SocialAccount.objects.values('user_id')
                            .annotate(cnt=Count('id'))
                            .filter(cnt__gte=2)
                            .count()
                        )
                        recent_sso_logins = (
                            User.objects.filter(
                                last_login__gte=n - timedelta(days=7),
                                last_login__isnull=False,
                                socialaccount__isnull=False,
                            ).distinct().count()
                        )
                        return {
                            'providers': providers_list,
                            'multi_conn': multi_conn,
                            'recent_logins': recent_sso_logins
                        }

                    sso_stats = cache.get_or_set('admin_dashboard_sso_stats', _get_sso, 300)
                    ctx['sso_providers'] = sso_stats['providers']
                    ctx['sso_multi_conn_users'] = sso_stats['multi_conn']
                    ctx['sso_recent_logins'] = sso_stats['recent_logins']
                    ctx['sso_no_providers'] = not sso_stats['providers']
                    ctx['sso_unavailable'] = False
                else:
                    ctx['sso_section_enabled'] = False
            except (DatabaseError, RedisError):
                logger.exception('AdminDashboard: failed to load SSO section')
                ctx['sso_section_enabled'] = True
                ctx['sso_unavailable'] = True

            # Configuration Status
            try:
                smtp_ok = not (
                    not getattr(settings, 'EMAIL_HOST', None)
                    or getattr(settings, 'EMAIL_BACKEND', '') == 'django.core.mail.backends.dummy.EmailBackend'
                )

                sso_ok = None
                if apps.is_installed('allauth.socialaccount'):
                    try:
                        sso_ok = SocialApp.objects.exists() or bool(getattr(settings, 'SOCIALACCOUNT_PROVIDERS', None))
                    except DatabaseError:
                        logger.warning("SocialApp table not available for SSO config status check.")
                        sso_ok = False

                ctx['config_smtp_ok'] = smtp_ok
                ctx['config_sso_ok'] = sso_ok
                ctx['config_status_unavailable'] = False
            except (DatabaseError, RedisError):
                logger.exception('AdminDashboard: failed to load config status section')
                ctx['config_status_unavailable'] = True

            # API & Integration Status
            try:
                api_stats = cache.get_or_set(
                    'admin_dashboard_api_stats',
                    lambda: {
                        'active_oauth_apps': OAuthApplication.objects.filter(active=True).count(),
                        'active_tokens': (
                            TeamAPIToken.objects.filter(active=True).count()
                            + OAuthAccessToken.objects.filter(expires__gt=n).count()
                        ),
                        'active_webhooks': WebHook.objects.filter(enabled=True).count(),
                        'webhook_calls_24h': WebHookCall.objects.filter(datetime__gte=n - timedelta(hours=24)).count(),
                        'webhook_failed_24h': WebHookCall.objects.filter(datetime__gte=n - timedelta(hours=24), success=False).count(),
                        'webhook_success_24h': WebHookCall.objects.filter(datetime__gte=n - timedelta(hours=24), success=True).count(),
                    },
                    300
                )
                ctx['active_oauth_apps'] = api_stats['active_oauth_apps']
                ctx['active_tokens'] = api_stats['active_tokens']
                ctx['active_webhooks_count'] = api_stats['active_webhooks']
                ctx['webhook_calls_24h'] = api_stats['webhook_calls_24h']
                ctx['webhook_failed_24h'] = api_stats['webhook_failed_24h']
                total_wh = api_stats['webhook_calls_24h']
                success_wh = api_stats['webhook_success_24h']
                ctx['webhook_success_rate'] = (
                    round((success_wh / total_wh) * 100, 1) if total_wh > 0 else None
                )
                ctx['api_version'] = __version__
                ctx['api_status_unavailable'] = False
            except (DatabaseError, RedisError):
                logger.exception('AdminDashboard: failed to load API status section')
                ctx['api_status_unavailable'] = True

        ctx['video_server_rows'] = get_video_server_dashboard_rows()

        return ctx


class OrganizerList(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'pretixcontrol/admin/organizers.html'

    def get_queryset(self):
        qs = Organizer.objects.all()
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        return ctx

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class AdminEventList(AdministratorPermissionRequiredMixin, EventList):
    """Inherit from EventList to add a custom template for the admin event list."""

    template_name = 'pretixcontrol/admin/events/index.html'

    def get_queryset(self):
        # Keep settings prefetched for component test-mode state checks in the list.
        return super().get_queryset().prefetch_related('_settings_objects')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for event in ctx.get('events', []):
            event.component_testmode = event.has_component_testmode
            event.startpage_toggle_locked = bool(event.component_testmode or not event.live)
        return ctx


class AdminEventStartpageToggle(AdministratorPermissionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        data = request.POST
        if not data:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except (ValueError, AttributeError):
                data = {}

        event_id = data.get('event_id')
        field = data.get('field')
        value = data.get('value')

        if field not in {'startpage_visible', 'startpage_featured'}:
            return JsonResponse({'ok': False, 'error': _('Invalid field.')}, status=400)
        if event_id is None:
            return JsonResponse({'ok': False, 'error': _('Event not found.')}, status=404)

        event = get_object_or_404(Event, pk=event_id)
        enable = str(value).lower() in {'true', '1', 'yes', 'on'}

        if event.has_component_testmode or not event.live:
            return JsonResponse(
                {
                    'ok': False,
                    'error': _('Only published events without test mode can be shown on the start page.'),
                },
                status=400,
            )

        if field == 'startpage_featured':
            event.startpage_featured = enable
            if enable:
                event.startpage_visible = True
            event.save(update_fields=['startpage_featured', 'startpage_visible'])
        else:
            event.startpage_visible = enable
            if not enable and event.startpage_featured:
                event.startpage_featured = False
            event.save(update_fields=['startpage_visible', 'startpage_featured'])

        return JsonResponse(
            {
                'ok': True,
                'startpage_visible': event.startpage_visible,
                'startpage_featured': event.startpage_featured,
                'startpage_locked': bool(event.has_component_testmode or not event.live),
            }
        )


class AttendeeListView(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/attendees/index.html'
    context_object_name = 'attendees'
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        with scopes_disabled():
            return super().get(request, *args, **kwargs)

    @cached_property
    def filter_form(self):
        return AttendeeFilterForm(data=self.request.GET)

    def get_queryset(self):
        qs = (
            OrderPosition.objects.select_related('order', 'product', 'order__event', 'order__event__organizer')
            .prefetch_related(
                Prefetch(
                    'checkins',
                    queryset=Checkin.objects.order_by('-datetime'),
                )
            )
            .filter(order__status='p')
        )

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')
        ordering_map = {
            'name': 'attendee_name_cached',
            '-name': '-attendee_name_cached',
            'email': 'attendee_email',
            '-email': '-attendee_email',
            'event': 'order__event__name',
            '-event': '-order__event__name',
            'order_code': 'order__code',
            '-order_code': '-order__code',
            'product': 'product__name',
            '-product': '-product__name',
        }

        if ordering in ordering_map:
            qs = qs.order_by(ordering_map[ordering])
        else:
            qs = qs.order_by('-order__event__date_from', 'order__event__name')

        return qs

    @staticmethod
    def _checkin_status(pos):
        def parse_dt(dt):
            if not dt:
                return None
            return dt if is_aware(dt) else make_aware(dt, UTC)

        checkins = pos.checkins.all()
        entry_time = parse_dt(next((c.datetime for c in checkins if c.type == Checkin.TYPE_ENTRY), None))
        exit_time = parse_dt(next((c.datetime for c in checkins if c.type == Checkin.TYPE_EXIT), None))

        if not entry_time and not exit_time:
            return 'Not checked in'
        if entry_time and not exit_time:
            return 'Checked in'
        if not entry_time and exit_time:
            return 'Checked out (no entry record)'
        if exit_time < entry_time:
            return 'Invalid check-in data (exit before entry)'
        if exit_time == entry_time:
            return 'Checked in and out at same time'
        return 'Checked in but left'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        ctx['attendees'] = [
            {
                'name': pos.attendee_name_cached or '',
                'email': pos.attendee_email or pos.order.email,
                'event': pos.order.event.name,
                'event_slug': pos.order.event.slug,
                'organizer_slug': pos.order.event.organizer.slug,
                'order_code': pos.order.code,
                'product': str(pos.product.name),
                'check_in_status': self._checkin_status(pos),
                'testmode': pos.order.testmode,
            }
            for pos in ctx['attendees']
        ]
        return ctx


class SubmissionListView(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/submissions/index.html'
    context_object_name = 'submissions'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return SubmissionFilterForm(data=self.request.GET)

    def get(self, request, *args, **kwargs):
        with scopes_disabled():
            return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Submission.objects.select_related(
                'event', 'event__organizer', 'submission_type', 'track'
            )
            .prefetch_related('speakers', 'tags')
        )

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')
        ordering_map = {
            'title': 'title',
            '-title': '-title',
            'event': 'event__name',
            '-event': '-event__name',
            'speakers': 'speakers__fullname',
            '-speakers': '-speakers__fullname',
            'state': 'state',
            '-state': '-state',
            'session_type': 'submission_type__name',
            '-session_type': '-submission_type__name',
        }

        if ordering in ordering_map:
            qs = qs.order_by(ordering_map[ordering])
        else:
            qs = qs.order_by('-event__date_from', 'title')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        ctx['submissions'] = [
            {
                'title': s.title,
                'speakers': [{'name': sp.get_display_name(), 'code': sp.code} for sp in s.speakers.all()],
                'speakers_string': ', '.join(sp.get_display_name() for sp in s.speakers.all()),
                'event': s.event.name,
                'session_type': s.submission_type.name if s.submission_type else '',
                'proposal_state': s.state,
                'event_slug': s.event.slug,
                'organizer_slug': s.event.organizer.slug,
                'code': s.code,
                'track': s.track.name if s.track else '',
                'tags': ', '.join(t.tag for t in s.tags.all()),
                'tags_list': [t.tag for t in s.tags.all()],
            }
            for s in ctx['submissions']
        ]
        return ctx


class AdminOrderListView(PaginationMixin, AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/orders/index.html'
    context_object_name = 'orders'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return AdminOrderFilterForm(data=self.request.GET)

    def get(self, request, *args, **kwargs):
        with scopes_disabled():
            return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Order.objects.select_related('event', 'event__organizer')

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')
        ordering_map = {
            'code': 'code',
            '-code': '-code',
            'email': 'email',
            '-email': '-email',
            'event': 'event__name',
            '-event': '-event__name',
            'organizer': 'event__organizer__name',
            '-organizer': '-event__organizer__name',
            'status': 'status',
            '-status': '-status',
            'total': 'total',
            '-total': '-total',
            'date': 'datetime',
            '-date': '-datetime',
        }
        sort_field = ordering_map.get(ordering, '-datetime')
        tie_breaker = '-pk' if sort_field.startswith('-') else 'pk'
        qs = qs.order_by(sort_field, tie_breaker)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['orders'] = [
            {
                'order_code': o.code,
                'event': o.event.name,
                'event_slug': o.event.slug,
                'organizer': o.event.organizer.name,
                'organizer_slug': o.event.organizer.slug,
                'email': o.email or '',
                'status': o.get_status_display(),
                'status_code': o.status,
                'total': o.total,
                'currency': o.event.currency,
                'date': o.datetime,
                'testmode': o.testmode,
            }
            for o in ctx['orders']
        ]
        return ctx


class TaskList(AdministratorPermissionRequiredMixin, PaginationMixin, ListView):
    template_name = 'pretixcontrol/admin/task_management/task_management.html'
    context_object_name = 'tasks'
    model = PeriodicTask

    @cached_property
    def filter_form(self):
        return TaskFilterForm(data=self.request.GET)

    def get_queryset(self):
        queryset = (super().get_queryset().exclude(name='celery.backend_cleanup').select_related('crontab', 'interval', 'solar', 'clocked'))

        if self.filter_form.is_valid():
            queryset = self.filter_form.filter_qs(queryset)

        return queryset

    def process_task_data(self, task):
        if task.last_run_at is None:
            task.formatted_last_run_at = '-'
        else:
            local_timezone = ZoneInfo(settings.TIME_ZONE)
            task.formatted_last_run_at = date_format(
                localtime(task.last_run_at, local_timezone), format='M. d, Y, g:i a'
            )

        task.name = task.name.replace('_', ' ').capitalize()

        options = Options()
        options.locale_code = settings.LANGUAGE_CODE
        options.verbose = True
        schedule = task.crontab
        if schedule:
            cron_expression = (
                f'{schedule.minute} {schedule.hour} {schedule.day_of_month} {schedule.month_of_year} {schedule.day_of_week}'
            )
            task.run_at = get_description(cron_expression, options)
        elif task.interval:
            task.run_at = f"Every {task.interval.every} {task.interval.period}"
        elif task.solar:
            task.run_at = f"Solar: {task.solar.event}"
        elif task.clocked:
            task.run_at = f"Clocked: {task.clocked.clocked_time}"
        else:
            task.run_at = "-"

        return task

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['tasks'] = [self.process_task_data(task) for task in context['tasks']]

        context['filter_form'] = self.filter_form
        return context

    def post(self, request, *args, **kwargs):
        task_id = request.POST.get('task_id')
        current_enabled = request.POST.get('enabled') == 'true'

        if task_id:
            task = get_object_or_404(PeriodicTask, id=task_id)
            new_status = not current_enabled

            PeriodicTask.objects.filter(id=task_id).update(enabled=new_status)
            PeriodicTasks.changed(task)

            status_text = 'enabled' if new_status else 'disabled'
            messages.success(
                self.request,
                f'The task {task.name} has been successfully {status_text}.',
            )

        return HttpResponseRedirect(reverse('eventyay_admin:admin.task_management'))


class VoucherList(PaginationMixin, AdministratorPermissionRequiredMixin, ListView):
    model = InvoiceVoucher
    context_object_name = 'vouchers'
    template_name = 'pretixcontrol/admin/vouchers/index.html'

    def get_queryset(self):
        qs = InvoiceVoucher.objects.prefetch_related('limit_events', 'limit_organizer').all()

        # Apply tab filter
        tab = self.request.GET.get('tab', 'all')
        if tab == 'active':
            qs = qs.filter(status=InvoiceVoucher.STATUS_ACTIVE)
        elif tab == 'disabled':
            qs = qs.filter(status=InvoiceVoucher.STATUS_DISABLED)
        elif tab == 'draft':
            qs = qs.filter(status=InvoiceVoucher.STATUS_DRAFT)
        elif tab == 'expired':
            qs = qs.filter(
                status=InvoiceVoucher.STATUS_ACTIVE,
                valid_until__lt=now(),
            )
        elif tab == 'used_up':
            qs = qs.filter(
                status=InvoiceVoucher.STATUS_ACTIVE,
                redeemed__gte=F('max_usages'),
            )

        # Apply filter form
        self.filter_form = VoucherFilterForm(self.request.GET)
        if self.filter_form.is_valid():
            fdata = self.filter_form.cleaned_data

            if fdata.get('search'):
                search = fdata['search']
                qs = qs.filter(
                    Q(code__icontains=search)
                    | Q(limit_events__name__icontains=search)
                    | Q(limit_organizer__name__icontains=search)
                ).distinct()

            if fdata.get('status'):
                status_val = fdata['status']
                if status_val == 'active':
                    qs = qs.filter(status=InvoiceVoucher.STATUS_ACTIVE)
                elif status_val == 'disabled':
                    qs = qs.filter(status=InvoiceVoucher.STATUS_DISABLED)
                elif status_val == 'draft':
                    qs = qs.filter(status=InvoiceVoucher.STATUS_DRAFT)
                elif status_val == 'expired':
                    qs = qs.filter(
                        status=InvoiceVoucher.STATUS_ACTIVE,
                        valid_until__lt=now(),
                    )
                elif status_val == 'used_up':
                    qs = qs.filter(
                        status=InvoiceVoucher.STATUS_ACTIVE,
                        redeemed__gte=F('max_usages'),
                    )

            if fdata.get('effect'):
                qs = qs.filter(price_mode=fdata['effect'])

            if fdata.get('scope'):
                scope_val = fdata['scope']
                if scope_val == 'events':
                    qs = qs.filter(limit_events__isnull=False).distinct()
                elif scope_val == 'organisers':
                    qs = qs.filter(limit_organizer__isnull=False).distinct()
                elif scope_val == 'platform_wide':
                    qs = qs.filter(limit_events__isnull=True, limit_organizer__isnull=True)

            if fdata.get('valid_until'):
                qs = qs.filter(valid_until__date__lte=fdata['valid_until'])

        # Ordering
        ordering = self.request.GET.get('ordering', '-updated_at')
        allowed_orderings = {
            'code', '-code', 'valid_until', '-valid_until',
            'redeemed', '-redeemed', 'updated_at', '-updated_at',
        }
        if ordering in allowed_orderings:
            qs = qs.order_by(ordering)

        return qs

    def _get_status_counts(self):
        """Compute counts for each status tab."""
        all_qs = InvoiceVoucher.objects.all()
        now_dt = now()
        return {
            'all': all_qs.count(),
            'active': all_qs.filter(
                status=InvoiceVoucher.STATUS_ACTIVE,
            ).exclude(
                valid_until__lt=now_dt,
            ).exclude(
                redeemed__gte=F('max_usages'),
            ).count(),
            'disabled': all_qs.filter(status=InvoiceVoucher.STATUS_DISABLED).count(),
            'expired': all_qs.filter(
                status=InvoiceVoucher.STATUS_ACTIVE,
                valid_until__lt=now_dt,
            ).count(),
            'used_up': all_qs.filter(
                status=InvoiceVoucher.STATUS_ACTIVE,
                redeemed__gte=F('max_usages'),
            ).count(),
            'draft': all_qs.filter(status=InvoiceVoucher.STATUS_DRAFT).count(),
        }

    def _get_summary_stats(self):
        """Compute summary card statistics."""
        all_qs = InvoiceVoucher.objects.all()
        now_dt = now()

        active_count = all_qs.filter(
            status=InvoiceVoucher.STATUS_ACTIVE,
        ).exclude(
            valid_until__lt=now_dt,
        ).exclude(
            redeemed__gte=F('max_usages'),
        ).count()

        used_count = all_qs.filter(redeemed__gt=0).count()

        expired_count = all_qs.filter(
            status=InvoiceVoucher.STATUS_ACTIVE,
            valid_until__lt=now_dt,
        ).count()

        disabled_count = all_qs.filter(status=InvoiceVoucher.STATUS_DISABLED).count()

        # Total fee waived as percentage-based summary
        total_vouchers = all_qs.count()
        used_vouchers = all_qs.filter(redeemed__gt=0).count()
        total_waived_pct = round((used_vouchers / total_vouchers * 100), 1) if total_vouchers > 0 else 0

        return {
            'active_count': active_count,
            'used_count': used_count,
            'expired_count': expired_count,
            'disabled_count': disabled_count,
            'total_waived_pct': total_waived_pct,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form if hasattr(self, 'filter_form') else VoucherFilterForm()
        ctx['status_counts'] = self._get_status_counts()
        ctx['stats'] = self._get_summary_stats()
        ctx['current_tab'] = self.request.GET.get('tab', 'all')
        return ctx


class VoucherCreate(AdministratorPermissionRequiredMixin, CreateView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/form.html'
    context_object_name = 'voucher'

    def get_form_class(self):
        return InvoiceVoucherForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currency'] = settings.DEFAULT_CURRENCY
        ctx['creating'] = True
        return ctx

    def get_success_url(self) -> str:
        return reverse('eventyay_admin:admin.global.business') + '#tab-event_vouchers'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = str(self.request.user)
        form.instance.updated_by = str(self.request.user)
        messages.success(self.request, _('Platform fee voucher has been created.'))
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VoucherUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/form.html'
    context_object_name = 'voucher'

    def get_form_class(self):
        return InvoiceVoucherForm

    def get_object(self, queryset=None) -> InvoiceVoucher:
        try:
            return InvoiceVoucher.objects.prefetch_related(
                'limit_events', 'limit_organizer'
            ).get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currency'] = settings.DEFAULT_CURRENCY
        ctx['creating'] = False
        return ctx

    def form_valid(self, form):
        form.instance.updated_by = str(self.request.user)
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse('eventyay_admin:admin.global.business') + '#tab-event_vouchers'


class VoucherDetail(AdministratorPermissionRequiredMixin, DetailView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/detail.html'
    context_object_name = 'voucher'

    def get_object(self, queryset=None) -> InvoiceVoucher:
        try:
            return InvoiceVoucher.objects.prefetch_related(
                'limit_events', 'limit_organizer'
            ).get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))


class VoucherDisable(AdministratorPermissionRequiredMixin, DetailView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/disable.html'
    context_object_name = 'voucher'

    def get_object(self, queryset=None) -> InvoiceVoucher:
        try:
            return InvoiceVoucher.objects.get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def post(self, request, *args, **kwargs):
        voucher = self.get_object()
        voucher.status = InvoiceVoucher.STATUS_DISABLED
        voucher.updated_by = str(request.user)
        voucher.save(update_fields=['status', 'updated_by', 'updated_at'])
        messages.success(request, _('The voucher has been disabled.'))
        return HttpResponseRedirect(reverse('eventyay_admin:admin.vouchers'))


class VoucherDuplicate(AdministratorPermissionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            original = InvoiceVoucher.objects.prefetch_related(
                'limit_events', 'limit_organizer'
            ).get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

        # Create a copy as draft with a new code
        new_voucher = InvoiceVoucher(
            code=generate_code(),
            max_usages=original.max_usages,
            budget=original.budget,
            valid_until=original.valid_until,
            price_mode=original.price_mode,
            value=original.value,
            status=InvoiceVoucher.STATUS_DRAFT,
            comment=original.comment,
            allow_partial_usage=original.allow_partial_usage,
            created_by=str(request.user),
            updated_by=str(request.user),
        )
        new_voucher.save()
        new_voucher.limit_events.set(original.limit_events.all())
        new_voucher.limit_organizer.set(original.limit_organizer.all())

        messages.success(request, _('Voucher duplicated as draft with code %(code)s.') % {'code': new_voucher.code})
        return HttpResponseRedirect(
            reverse('eventyay_admin:admin.voucher', kwargs={'voucher': new_voucher.pk})
        )


class VoucherDelete(AdministratorPermissionRequiredMixin, DeleteView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/delete.html'
    context_object_name = 'voucher'

    def get_object(self, queryset=None) -> InvoiceVoucher:
        try:
            return InvoiceVoucher.objects.get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.allow_delete():
            messages.error(
                request,
                _('This voucher cannot be deleted. Only unredeemed draft vouchers can be deleted. '
                  'Disable the voucher instead.'),
            )
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()

        if not self.object.allow_delete():
            messages.error(
                self.request,
                _('This voucher cannot be deleted. Only unredeemed draft vouchers can be deleted.'),
            )
        else:
            self.object.delete()
            messages.success(self.request, _('The selected voucher has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse('eventyay_admin:admin.global.business') + '#tab-event_vouchers'


class SystemConfigView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/systemconfig.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_name'] = settings.INSTANCE_NAME
        context['base_path'] = settings.BASE_PATH
        context['settings'] = settings
        return context

    @context
    def queue_length(self):
        if settings.CELERY_TASK_ALWAYS_EAGER:
            return None
        try:
            client = app.broker_connection().channel().client
            return client.llen('celery')
        except Exception as e:
            return str(e)

    @context
    def executable(self):
        return sys.executable

    @context
    def eventyay_version(self):
        return settings.EVENTYAY_VERSION


class UpdateCheckView(AdministratorPermissionRequiredMixin, FormView):
    template_name = 'pretixcontrol/admin/update.html'
    form_class = UpdateSettingsForm

    def post(self, request, *args, **kwargs):
        if 'trigger' in request.POST:
            update_check.apply()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, phrases.base.error_saving_changes)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['gs'] = GlobalSettings()
        result['gs'].settings.set('update_check_ack', True)
        return result

    @context
    def result_table(self):
        return check_result_table()

    def get_success_url(self):
        return reverse('eventyay_admin:admin.update')
