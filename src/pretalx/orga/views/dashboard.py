from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.models.log import ActivityLog
from pretalx.event.stages import get_stages
from pretalx.submission.models.submission import SubmissionStates


class DashboardView(TemplateView):
    template_name = 'orga/dashboard.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['organisers'] = set(
            team.organiser for team in
            self.request.user.teams.filter(can_change_organiser_settings=True)
        )
        return context


class EventDashboardView(PermissionRequired, TemplateView):
    template_name = 'orga/event/dashboard.html'
    permission_required = 'orga.view_orga_area'

    def get_object(self):
        return self.request.event

    def get_context_data(self, event):
        context = super().get_context_data()
        event = self.request.event
        context['timeline'] = get_stages(event)
        context['history'] = ActivityLog.objects.filter(event=self.get_object())[:20]
        context['tiles'] = []
        today = now().date()
        if today < event.date_from:
            context['tiles'].append({
                'large': (event.date_from - today).days,
                'small': _('days until event start'),
            })
        elif today > event.date_to:
            context['tiles'].append({
                'large': (today - event.date_from).days,
                'small': _('days since event end'),
            })
        else:
            day = (today - event.date_from).days + 1
            context['tiles'].append({
                'large': _('Day {number}').format(number=day),
                'small': _('of {total_days} days').format(total_days=(event.date_to - event.date_from).days + 1),
                'url': event.urls.schedule + f'#{today.isoformat()}',
            })
        if event.current_schedule:
            context['tiles'].append({
                'large': event.current_schedule.version,
                'small': _('current schedule'),
                'url': event.urls.schedule,
            })
        context['tiles'].append({
            'url': event.urls.base,
            'small': _('Go to CfP'),
        })
        if event.submissions.count():
            context['tiles'].append({
                'large': event.submissions.count(),
                'small': _('total submissions'),
                'url': event.orga_urls.submissions,
            })
            talk_count = event.talks.count()
            if talk_count:
                context['tiles'].append({
                    'large': talk_count,
                    'small': _('total talks'),
                    'url': event.orga_urls.submissions,
                })
                confirmed_count = event.talks.filter(state=SubmissionStates.CONFIRMED).count()
                if confirmed_count != talk_count:
                    context['tiles'].append({
                        'large': talk_count - confirmed_count,
                        'small': _('unconfirmed talks'),
                        'url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
                    })
        if event.speakers.count():
            context['tiles'].append({
                'large': event.speakers.count(),
                'small': _('speakers'),
                'url': event.orga_urls.speakers,
            })
        context['tiles'].append({
            'large': event.queued_mails.filter(sent__isnull=False).count(),
            'small': _('sent emails'),
            'url': event.orga_urls.send_mails,
        })
        return context
