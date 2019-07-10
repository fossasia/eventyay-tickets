import copy

from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from pretalx.submission.models import SubmissionStates


def _is_in_preparation(event):
    return not event.is_public and now() <= event.datetime_from


def _is_cfp_open(event):
    return not _is_in_preparation(event) and event.cfp.is_open


def _is_in_review(event):
    return (
        not _is_cfp_open(event)
        and event.submissions.filter(state=SubmissionStates.SUBMITTED).exists()
        and now() <= event.datetime_from
    )


def _is_in_scheduling_stage(event):
    return (
        not _is_running(event) and not _is_in_wrapup(event) and not _is_in_review(event)
    )


def _is_running(event):
    return event.datetime_from <= now() <= event.datetime_to


def _is_in_wrapup(event):
    return event.datetime_to <= now()


STAGES = {
    'PREPARATION': {
        'name': _('Preparation'),
        'method': _is_in_preparation,
        'icon': 'paper-plane',
        'links': [
            {'title': _('Configure the event'), 'url': ['orga_urls', 'settings']},
            {'title': _('Gather your team'), 'url': ['organiser', 'orga_urls', 'base']},
            {'title': _('Write a CfP'), 'url': ['cfp', 'urls', 'edit_text']},
            {
                'title': _('Customize mail templates'),
                'url': ['orga_urls', 'mail_templates'],
            },
        ],
    },
    'CFP_OPEN': {
        'name': _('CfP is open'),
        'method': _is_cfp_open,
        'icon': 'bullhorn',
        'links': [
            {'title': _('Monitor submissions'), 'url': ['orga_urls', 'submissions']},
            {
                'title': _('Submit talks for your speakers'),
                'url': ['orga_urls', 'new_submission'],
            },
            {'title': _('Invite reviewers'), 'url': ['organiser', 'orga_urls', 'base']},
        ],
    },
    'REVIEW': {
        'name': _('Review'),
        'method': _is_in_review,
        'icon': 'eye',
        'links': [
            {'title': _('Let reviewers do their work')},
            {
                'title': _('Accept or reject submissions'),
                'url': ['orga_urls', 'submissions'],
            },
            {'title': _('Build your first schedule'), 'url': ['orga_urls', 'schedule']},
        ],
    },
    'SCHEDULE': {
        'name': _('Schedule'),
        'method': _is_in_scheduling_stage,
        'icon': 'calendar-o',
        'links': [
            {
                'title': _('Release schedules as needed'),
                'url': ['orga_urls', 'schedule'],
            },
            {
                'title': _('Inform your speakers about the infrastructure'),
                'url': ['orga_urls', 'compose_mails'],
            },
        ],
    },
    'EVENT': {
        'name': _('Event'),
        'method': _is_running,
        'icon': 'play',
        'links': [
            {'title': _('Provide a point of contact for the speakers')},
            {'title': _('Enjoy the event!')},
        ],
    },
    'WRAPUP': {
        'name': _('Wrapup'),
        'method': _is_in_wrapup,
        'icon': 'pause',
        'links': [
            {'title': _('Monitor incoming feedback')},
            {'title': _('Embed talk recordings if available')},
            {'title': _('Release next event date?')},
        ],
    },
}
STAGE_ORDER = ['PREPARATION', 'CFP_OPEN', 'REVIEW', 'SCHEDULE', 'EVENT', 'WRAPUP']


def in_stage(event, stage):
    return STAGES[stage]['method'](event)


def build_event_url(event, url):
    result = event
    for part in url:
        result = getattr(result, part)
    return result


def get_stages(event):
    inactive_state = 'done'
    stages = copy.deepcopy(STAGES)

    for stage in STAGES:
        is_stage_active = inactive_state == 'done' and in_stage(event, stage)
        if is_stage_active:
            inactive_state = 'todo'
        stages[stage]['phase'] = 'current' if is_stage_active else inactive_state
        for link in stages[stage].get('links', []):
            if 'url' in link and link['url']:
                link['url'] = build_event_url(event, link['url'])
    return stages
