from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.defaultfilters import timeuntil
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import TemplateView
from django_context_decorator import context
from django_scopes import scope, scopes_disabled

from django.http import Http404

def legacy_orga_event_redirect(request, event):
    from eventyay.base.models import Event
    with scopes_disabled():
        events = Event.objects.filter(slug__iexact=event)
        if events.count() == 1:
            e = events.first()
            url = f"/orga/event/{e.organizer.slug}/{e.slug}/"
            if request.META.get('QUERY_STRING'):
                url += '?' + request.META['QUERY_STRING']
            return redirect(url, permanent=True)
        if events.count() > 1 and request.user.is_authenticated:
            user_events = events.filter(
                Q(organizer__id__in=request.user.teams.values_list('organizer_id', flat=True)) |
                Q(submissions__speakers__in=[request.user])
            ).distinct()
            if user_events.count() == 1:
                e = user_events.first()
                url = f"/orga/event/{e.organizer.slug}/{e.slug}/"
                if request.META.get('QUERY_STRING'):
                    url += '?' + request.META['QUERY_STRING']
                return redirect(url, permanent=True)
        raise Http404()

from eventyay.base.models import Review, Submission, SubmissionStates
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.event import Event
from eventyay.base.models.log import LogEntry
from eventyay.base.models.organizer import Organizer
from eventyay.base.settings import is_event_series_creation_enabled, is_meetup_creation_enabled
from eventyay.common.text.phrases import phrases
from eventyay.common.permissions import is_admin_mode_active
from eventyay.common.views.mixins import EventPermissionRequired, PermissionRequired
from eventyay.event.stages import get_stages
from eventyay.orga.views.submission import SubmissionStatsMixin
from eventyay.talk_rules.submission import get_missing_reviews


def start_redirect_view(request):
    with scopes_disabled():
        orga_events = set(request.user.get_events_with_any_permission())
        speaker_events = set(Event.objects.filter(submissions__speakers__in=[request.user]))

    # Users with only one event, in only one role, are redirected to that event
    if len(orga_events | speaker_events) == 1 and not (orga_events and speaker_events):
        if orga_events:
            return redirect(orga_events.pop().orga_urls.base)
        return redirect(speaker_events.pop().urls.user_submissions)

    return redirect(reverse('eventyay_common:dashboard'))


class DashboardEventListView(TemplateView):
    template_name = 'orga/event_list.html'

    @property
    def base_queryset(self):
        return self.request.user.get_events_with_any_permission()

    @cached_property
    def queryset(self):
        if is_admin_mode_active(self.request):
            qs = Event.objects.all()
        else:
            qs = self.base_queryset.annotate(
                submission_count=Count(
                    'submissions',
                    filter=Q(
                        submissions__state__in=[
                            state
                            for state in SubmissionStates.display_values.keys()
                            if state not in (SubmissionStates.DELETED, SubmissionStates.DRAFT)
                        ]
                    ),
                )
            ).order_by('-date_from')
        if search := self.request.GET.get('q'):
            qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_orga_events'] = []
        context['past_orga_events'] = []
        for event in self.queryset:
            if event.date_to >= now():
                context['current_orga_events'].insert(0, event)
            else:
                context['past_orga_events'].append(event)
        context['speaker_events'] = (
            Event.objects.filter(submissions__speakers__in=[self.request.user]).distinct().order_by('-date_from')
        )
        context['event_series_creation_enabled'] = is_event_series_creation_enabled(self.request)
        context['meetup_creation_enabled'] = is_meetup_creation_enabled(self.request)
        return context


class DashboardOrganizerEventListView(PermissionRequired, DashboardEventListView):
    permission_required = 'base.view_organizer'

    def get_permission_object(self):
        return self.request.organizer

    @property
    def base_queryset(self):
        return self.request.organizer.events.all()

    @context
    def hide_speaker_events(self):
        return True


class DashboardOrganizerListView(PermissionRequired, TemplateView):
    template_name = 'orga/organizer/list.html'
    permission_required = 'base.list_organizer'

    def filter_organizer(self, organizer, query):
        name = {'en': organizer.name} if isinstance(organizer.name, str) else organizer.name.data
        name = {'en': name} if isinstance(name, str) else name
        return query in organizer.slug or any(query in value for value in name.values())

    @context
    def organizers(self):
        if self.request.user.is_administrator:
            orgs = Organizer.objects.all()
        else:
            orgs = Organizer.objects.filter(
                pk__in={
                    team.organizer_id for team in self.request.user.teams.filter(can_change_organizer_settings=True)
                }
            )
        orgs = orgs.annotate(
            event_count=Count('events', distinct=True),
            team_count=Count('teams', distinct=True),
        )
        query = self.request.GET.get('q')
        if not query:
            return orgs
        query = query.lower().strip()
        return [org for org in orgs if self.filter_organizer(org, query)]


class EventDashboardView(EventPermissionRequired, SubmissionStatsMixin, TemplateView):
    template_name = 'orga/event/dashboard.html'
    permission_required = 'base.talk_orga_access_event'

    def post(self, request, *args, **kwargs):
        if 'internal_note' in request.POST:
            if not request.user.has_perm('base.update_event', request.event):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied()
            internal_note = request.POST.get('internal_note', '')[:1000]
            request.event.comment = internal_note
            request.event.save(update_fields=['comment'])
            from django.contrib import messages
            from django.utils.translation import gettext as _
            messages.success(request, _('Internal note saved.'))
            return redirect(request.path)
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])

    def enhance_timeline(self, event, stages):
        from django.utils.translation import gettext as _
        from eventyay.base.models import SubmissionStates
        
        status_map = {
            'done': _('Completed'),
            'current': _('In progress'),
            'todo': _('Pending'),
        }

        for key, stage in stages.items():
            stage['status_text'] = status_map.get(stage.get('phase'), '')
            stage['summary'] = ''

            if key == 'CFP_OPEN' and hasattr(event, 'cfp') and getattr(event.cfp, 'max_deadline', None):
                if stage['phase'] == 'current':
                    stage['summary'] = event.cfp.max_deadline.strftime('%b %d')
                elif stage['phase'] == 'done':
                    stage['summary'] = _('{count} submitted').format(count=event.submissions.count())

            elif key == 'REVIEW':
                rejected = event.submissions.filter(state=SubmissionStates.REJECTED).count()
                if rejected > 0:
                    stage['summary'] = _('{count} rejected').format(count=rejected)

            elif key == 'SCHEDULE':
                from django.db.models import Q
                unscheduled = event.wip_schedule.talks.filter(
                    Q(start__isnull=True) | Q(room__isnull=True),
                    is_visible=True, submission__isnull=False
                ).count()
                
                if stage['phase'] == 'current' or unscheduled > 0:
                    stage['summary'] = _('{count} unscheduled').format(count=unscheduled)
                elif stage['phase'] == 'done':
                    scheduled = event.wip_schedule.talks.filter(
                        start__isnull=False, room__isnull=False, is_visible=True, submission__isnull=False
                    ).count()
                    if scheduled > 0:
                        stage['summary'] = _('{count} scheduled').format(count=scheduled)
        
        return list(stages.values())

    def get_cfp_tiles(self, _now, can_change_submissions=False):
        result = []
        if not hasattr(self.request.event, 'cfp'):
            return result
        if self.request.event.cfp.is_open and (
            self.request.event.talks_published
            or self.request.event.private_testmode_talks_enabled
        ):
            result.append(
                {
                    'url': self.request.event.cfp.urls.public,
                    'large': phrases.cfp.go_to_cfp,
                    'priority': 20,
                }
            )
        max_deadline = self.request.event.cfp.max_deadline
        if max_deadline and _now < max_deadline:
            result.append(
                {
                    'large': timeuntil(max_deadline),
                    'small': _('until the CfP ends'),
                    'priority': 40,
                }
            )
            draft_proposals = Submission.all_objects.filter(
                state=SubmissionStates.DRAFT, event=self.request.event
            ).count()
            if draft_proposals and can_change_submissions:
                result.append(
                    {
                        'large': draft_proposals,
                        'small': ngettext_lazy(
                            'unsubmitted proposal draft',
                            'unsubmitted proposal drafts',
                            draft_proposals,
                        ),
                        'priority': 50,
                        'url': self.request.event.orga_urls.send_drafts_reminder,
                        'left': {
                            'text': _('Send reminder'),
                            'url': self.request.event.orga_urls.send_drafts_reminder,
                            'color': 'info',
                        },
                    }
                )
        return result

    def get_review_tiles(self, can_change_settings):
        result = []
        review_count = self.request.event.reviews.count()
        if review_count:
            active_reviewers = (
                self.request.event.reviewers.filter(reviews__isnull=False).order_by('id').distinct().count()
            )
            result.append({'large': review_count, 'small': _('Reviews'), 'priority': 60})
            result.append(
                {
                    'large': active_reviewers,
                    'small': _('Active reviewers'),
                    'url': (self.request.event.organizer.orga_urls.teams if can_change_settings else None),
                    'priority': 60,
                }
            )
        is_reviewer = self.request.user.is_administrator or self.request.event.teams.filter(members__in=[self.request.user], is_reviewer=True).exists()
        if is_reviewer:
            reviews_missing = get_missing_reviews(self.request.event, self.request.user).count()
            if reviews_missing:
                result.append(
                    {
                        'large': reviews_missing,
                        'small': ngettext_lazy(
                            'proposal is waiting for your review.',
                            'proposals are waiting for your review.',
                            reviews_missing,
                        ),
                        'url': self.request.event.orga_urls.reviews,
                        'priority': 21,
                    }
                )
        return result

    @context
    def recent_talk_activity(self):
        return LogEntry.objects.filter(
            Q(action_type__contains='submission') |
            Q(action_type__contains='speaker') |
            Q(action_type__contains='talk') |
            Q(action_type__contains='cfp') |
            Q(action_type__contains='review'),
            event=self.request.event
        ).select_related('user', 'event')[:10]

    def get_context_data(self, **kwargs):
        # Tiles can have priorities
        # Priorities are meant to be between 0 and 100
        # 0 is the first tile, the go-live tile
        # 100+ is whatever can go to the very end
        # actions should be between 10 and 30, with 20 being the "go to cfp" action
        # general stats start at 50
        result = super().get_context_data(**kwargs)
        event = self.request.event
        stages = get_stages(event)
        
        result['timeline'] = self.enhance_timeline(event, stages)
        result['go_to_target'] = 'schedule' if stages['REVIEW']['phase'] == 'done' else 'cfp'
        _now = now()
        today = _now
        
        can_update_event = self.request.user.has_perm('base.update_event', event)
        can_change_settings = self.request.user.has_perm('base.change_settings.event', event)
        can_update_submission = self.request.user.has_perm('base.orga_update_submission', event)
        can_view_submission_stats = self.request.user.has_perm('base.orga_list_submission', event)
        can_edit_schedule = self.request.user.has_perm('base.orga_edit_schedule', event)
        can_view_schedule = self.request.user.has_perm('base.orga_view_schedule', event)
        can_list_speaker = self.request.user.has_perm('base.orga_list_speakerprofile', event)
        can_view_speakers = can_list_speaker
        can_send_mail = self.request.user.has_perm('base.list_queuedmail', event)
        can_view_mails = can_send_mail
        can_view_teams = can_change_settings
        
        result.update({
            'can_update_event': can_update_event,
            'can_change_settings': can_change_settings,
            'can_update_submission': can_update_submission,
            'can_view_submission_stats': can_view_submission_stats,
            'can_edit_schedule': can_edit_schedule,
            'can_view_schedule': can_view_schedule,
            'can_list_speaker': can_list_speaker,
            'can_view_speakers': can_view_speakers,
            'can_send_mail': can_send_mail,
            'can_view_mails': can_view_mails,
            'can_view_teams': can_view_teams,
            'can_review': self.request.user.is_administrator or event.teams.filter(members__in=[self.request.user], is_reviewer=True).exists(),
        })
        can_change_submissions = can_update_submission

        with scope(event=event):
            tiles = self.get_cfp_tiles(_now, can_change_submissions=can_change_submissions)
            if today < event.date_from:
                days = (event.date_from - today).days
                from django.utils.translation import ngettext_lazy
                tiles.append({
                    'large': days,
                    'small': ngettext_lazy('day until event start', 'days until event start', days),
                    'priority': 10,
                })
            elif today > event.date_to:
                days = (today - event.date_to).days
                from django.utils.translation import ngettext_lazy
                tiles.append({
                    'large': days,
                    'small': ngettext_lazy('day since event end', 'days since event end', days),
                    'priority': 80,
                })
            elif event.date_to != event.date_from:
                day = (today - event.date_from).days + 1
                total_days = (event.date_to - event.date_from).days + 1
                tiles.append({
                    'large': _('Day {number}').format(number=day),
                    'small': _('of {total_days} days').format(total_days=total_days),
                    'url': event.urls.schedule + f'#{today.isoformat()}',
                    'priority': 10,
                })
            result['upcoming_items'] = tiles

            # Action required metrics
            unconfirmed_sessions_count = event.submissions.filter(state=SubmissionStates.ACCEPTED).count()
        
            unscheduled_sessions_count = 0
            if getattr(event, 'wip_schedule', None):
                unscheduled_sessions_count = event.wip_schedule.talks.filter(
                    Q(start__isnull=True) | Q(room__isnull=True),
                    is_visible=True,
                    submission__state=SubmissionStates.CONFIRMED
                ).count()
            
            incomplete_speakers_count = SpeakerProfile.objects.filter(
                Q(event=event, user__in=event.speakers) &
                (Q(biography__isnull=True) | Q(biography='') | Q(user__avatar__isnull=True) | Q(user__avatar=''))
            ).distinct().count()

            pending_notifications_count = event.queued_mails.filter(sent__isnull=True).count()
        
            result['action_required'] = {
                'unconfirmed_sessions': unconfirmed_sessions_count,
                'unscheduled_sessions': unscheduled_sessions_count,
                'incomplete_speakers': incomplete_speakers_count,
                'pending_notifications': pending_notifications_count,
            }

            # At a glance metrics
            submitted_proposals_count = event.submissions.count()
            accepted_proposals_count = event.submissions.filter(state=SubmissionStates.ACCEPTED).count()
            confirmed_sessions_count = event.submissions.filter(state=SubmissionStates.CONFIRMED).count()
            conversion_percentage = (
                round(
                    ((accepted_proposals_count + confirmed_sessions_count) / submitted_proposals_count) * 100,
                    1,
                )
                if submitted_proposals_count
                else 0
            )

            scheduled_sessions_count = 0
            if getattr(event, 'current_schedule', None):
                scheduled_sessions_count = event.current_schedule.talks.filter(
                    start__isnull=False, room__isnull=False, is_visible=True, submission__isnull=False
                ).count()

            speakers_count = event.speakers.count()
        
            is_reviewer = self.request.user.is_administrator or event.teams.filter(members__in=[self.request.user], is_reviewer=True).exists()
            pending_reviews_count = get_missing_reviews(event, self.request.user).count() if is_reviewer else 0
            rejected_proposals_count = event.submissions.filter(state=SubmissionStates.REJECTED).count()
            withdrawn_proposals_count = event.submissions.filter(state__in=[SubmissionStates.WITHDRAWN, SubmissionStates.CANCELED]).count()
        
            emails_sent_count = event.queued_mails.filter(sent__isnull=False).count()
            current_schedule_version = getattr(event.current_schedule, 'version', None) if getattr(event, 'current_schedule', None) else None
        
            active_reviewers_count = Review.objects.filter(submission__event=event).values('user').distinct().count()

            result['at_a_glance'] = {
                'talk_component_status': getattr(event, 'talk_component_presale_status', None),
                'submitted_proposals': submitted_proposals_count,
                'accepted_proposals': accepted_proposals_count,
                'conversion_percentage': conversion_percentage,
                'confirmed_sessions': confirmed_sessions_count,
                'scheduled_sessions': scheduled_sessions_count,
                'speakers': speakers_count,
                'pending_reviews': pending_reviews_count,
                'rejected_proposals': rejected_proposals_count,
                'withdrawn_proposals': withdrawn_proposals_count,
                'emails_sent': emails_sent_count,
                'current_schedule_version': current_schedule_version,
                'active_reviewers': active_reviewers_count,
            }
        
        return result
