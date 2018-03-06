from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.models.log import ActivityLog
from pretalx.event.stages import get_stages
from pretalx.submission.models.submission import SubmissionStates


class DashboardView(TemplateView):
    template_name = 'orga/dashboard.html'


class EventDashboardView(PermissionRequired, TemplateView):
    template_name = 'orga/event/dashboard.html'
    permission_required = 'orga.view_orga_area'

    def get_object(self):
        return self.request.event

    def get_context_data(self, event):
        ctx = super().get_context_data()
        event = self.request.event
        ctx['timeline'] = get_stages(event)
        ctx['history'] = ActivityLog.objects.filter(event=self.get_object())[:20]
        ctx['tiles'] = []
        today = now().date()
        if today < event.date_from:
            ctx['tiles'].append({
                'large': (event.date_from - today).days,
                'small': _('days until event start'),
            })
        elif today > event.date_to:
            ctx['tiles'].append({
                'large': (today - event.date_from).days,
                'small': _('days since event end'),
            })
        else:
            day = (today - event.date_from).days + 1
            ctx['tiles'].append({
                'large': _('Day {number}').format(number=day),
                'small': _('of {total_days} days').format(total_days=(event.date_to - event.date_from).days + 1),
                'url': event.urls.schedule + f'#{today.isoformat()}',
            })
        if event.current_schedule:
            ctx['tiles'].append({
                'large': event.current_schedule.version,
                'small': _('current schedule'),
                'url': event.urls.schedule,
            })
        ctx['tiles'].append({
            'url': event.urls.base,
            'small': _('Go to CfP'),
        })
        if event.submissions.count():
            ctx['tiles'].append({
                'large': event.submissions.count(),
                'small': _('total submissions'),
                'url': event.orga_urls.submissions,
            })
            talk_count = event.talks.count()
            if talk_count:
                ctx['tiles'].append({
                    'large': talk_count,
                    'small': _('total talks'),
                    'url': event.orga_urls.submissions,
                })
                confirmed_count = event.talks.filter(state=SubmissionStates.CONFIRMED).count()
                if confirmed_count != talk_count:
                    ctx['tiles'].append({
                        'large': talk_count - confirmed_count,
                        'small': _('unconfirmed talks'),
                        'url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
                    })
        if event.speakers.count():
            ctx['tiles'].append({
                'large': event.speakers.count(),
                'small': _('speakers'),
                'url': event.orga_urls.speakers,
            })
        ctx['tiles'].append({
            'large': event.queued_mails.filter(sent__isnull=False).count(),
            'small': _('sent emails'),
            'url': event.orga_urls.send_mails,
        })
        return ctx
