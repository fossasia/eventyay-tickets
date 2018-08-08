from django.http import JsonResponse
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.models.log import ActivityLog
from pretalx.event.models import Organiser
from pretalx.event.stages import get_stages
from pretalx.submission.models.submission import SubmissionStates


class DashboardView(TemplateView):
    template_name = 'orga/dashboard.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if self.request.user.is_administrator:
            context['organisers'] = Organiser.objects.all()
        else:
            context['organisers'] = set(
                team.organiser
                for team in self.request.user.teams.filter(
                    can_change_organiser_settings=True
                )
            )
        now_date = now().date()
        context['current_orga_events'] = [
            e for e in self.request.orga_events if e.date_to >= now_date
        ]
        context['past_orga_events'] = [
            e for e in self.request.orga_events if e.date_to < now_date
        ]
        return context


class EventDashboardView(PermissionRequired, TemplateView):
    template_name = 'orga/event/dashboard.html'
    permission_required = 'orga.view_orga_area'

    def get_object(self):
        return self.request.event

    def get_cfp_tiles(self, event, _now):
        result = []
        max_deadline = event.cfp.max_deadline
        if max_deadline and _now < max_deadline:
            diff = max_deadline - _now
            if diff.days >= 3:
                result.append({'large': diff.days, 'small': _('days until CfP end')})
            else:
                hours = diff.seconds // 3600
                minutes = (diff.seconds // 60) % 60
                result.append(
                    {'large': f'{hours}:{minutes}h', 'small': _('until CfP end')}
                )
        if event.cfp.is_open:
            result.append({'url': event.urls.base, 'small': _('Go to CfP')})
        return result

    def get_context_data(self, event):
        context = super().get_context_data()
        event = self.request.event
        stages = get_stages(event)
        context['timeline'] = stages
        context['go_to_target'] = (
            'schedule' if stages['REVIEW']['state'] == 'done' else 'cfp'
        )
        context['history'] = ActivityLog.objects.filter(event=self.get_object())[:20]
        _now = now()
        today = _now.date()
        context['tiles'] = self.get_cfp_tiles(event, _now)
        if today < event.date_from:
            context['tiles'].append(
                {
                    'large': (event.date_from - today).days,
                    'small': _('days until event start'),
                }
            )
        elif today > event.date_to:
            context['tiles'].append(
                {
                    'large': (today - event.date_from).days,
                    'small': _('days since event end'),
                }
            )
        else:
            day = (today - event.date_from).days + 1
            context['tiles'].append(
                {
                    'large': _('Day {number}').format(number=day),
                    'small': _('of {total_days} days').format(
                        total_days=(event.date_to - event.date_from).days + 1
                    ),
                    'url': event.urls.schedule + f'#{today.isoformat()}',
                }
            )
        if event.current_schedule:
            context['tiles'].append(
                {
                    'large': event.current_schedule.version,
                    'small': _('current schedule'),
                    'url': event.urls.schedule,
                }
            )
        if event.submissions.count():
            context['tiles'].append(
                {
                    'large': event.submissions.count(),
                    'small': _('total submissions'),
                    'url': event.orga_urls.submissions,
                }
            )
            talk_count = event.talks.count()
            if talk_count:
                context['tiles'].append(
                    {
                        'large': talk_count,
                        'small': _('total talks'),
                        'url': event.orga_urls.submissions
                        + f'?state={SubmissionStates.ACCEPTED}&state={SubmissionStates.CONFIRMED}',
                    }
                )
                confirmed_count = event.talks.filter(
                    state=SubmissionStates.CONFIRMED
                ).count()
                if confirmed_count != talk_count:
                    context['tiles'].append(
                        {
                            'large': talk_count - confirmed_count,
                            'small': _('unconfirmed talks'),
                            'url': event.orga_urls.submissions
                            + f'?state={SubmissionStates.ACCEPTED}',
                        }
                    )
        if event.speakers.count():
            context['tiles'].append(
                {
                    'large': event.speakers.count(),
                    'small': _('speakers'),
                    'url': event.orga_urls.speakers + '?role=true',
                }
            )
        context['tiles'].append(
            {
                'large': event.queued_mails.filter(sent__isnull=False).count(),
                'small': _('sent emails'),
                'url': event.orga_urls.compose_mails,
            }
        )
        return context


def url_list(request, event=None):
    event = request.event
    permissions = request.user.get_permissions_for_event(event)
    urls = [
        {'name': _('Dashboard'), 'url': event.orga_urls.base},
        {'name': _('Submissions'), 'url': event.orga_urls.submissions},
        {'name': _('Talks'), 'url': event.orga_urls.submissions},
        {'name': _('Submitters'), 'url': event.orga_urls.speakers},
        {'name': _('Speakers'), 'url': event.orga_urls.speakers + '?role=true'},
    ]
    if 'can_change_event_settings' in permissions:
        urls += [
            {'name': _('Settings'), 'url': event.orga_urls.settings},
            {'name': _('Mail settings'), 'url': event.orga_urls.mail_settings},
            {'name': _('Room settings'), 'url': event.orga_urls.room_settings},
            {'name': _('CfP'), 'url': event.orga_urls.cfp},
        ]
    if 'can_change_submissions' in permissions:
        urls += [
            {'name': _('Mail outbox'), 'url': event.orga_urls.outbox},
            {'name': _('Compose mail'), 'url': event.orga_urls.compose_mails},
            {'name': _('Mail templates'), 'url': event.orga_urls.mail_templates},
            {'name': _('Sent mails'), 'url': event.orga_urls.sent_mails},
            {'name': _('Schedule'), 'url': event.orga_urls.schedule},
            {'name': _('Schedule exports'), 'url': event.orga_urls.schedule_export},
            {'name': _('Speaker information'), 'url': event.orga_urls.information},
        ]
    if 'is_reviewer' in permissions:
        urls += [{'name': _('Review dashboard'), 'url': event.orga_urls.reviews}]
    return JsonResponse({'results': urls})
