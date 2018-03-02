import copy

from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from pretalx.submission.models import SubmissionStates


def _is_in_preparation(event):
    return not event.is_public and now() <= event.datetime_from


def _is_cfp_open(event):
    return not _is_in_preparation(event) and event.cfp.is_open


def _is_in_review(event):
    return not _is_cfp_open(event) and event.submissions.filter(state=SubmissionStates.SUBMITTED).exists()


def _is_in_scheduling_stage(event):
    return not _is_running(event) and not _is_in_wrapup(event) and not _is_in_review(event)


def _is_running(event):
    return event.datetime_from <= now() <= event.datetime_to


def _is_in_wrapup(event):
    return event.datetime_to <= now()


STAGES = {
    'PREPARATION': {
        'name': _('Preparation'),
        'method': _is_in_preparation,
    },
    'CFP_OPEN': {
        'name': _('CfP is open'),
        'method': _is_cfp_open,
    },
    'REVIEW': {
        'name': _('Review'),
        'method': _is_in_review,
    },
    'SCHEDULE': {
        'name': _('Schedule'),
        'method': _is_in_scheduling_stage,
    },
    'EVENT': {
        'name': _('Event'),
        'method': _is_running,
    },
    'WRAPUP': {
        'name': _('Wrapup'),
        'method': _is_in_wrapup,
    },
}
STAGE_ORDER = ['PREPARATION', 'CFP_OPEN', 'REVIEW', 'SCHEDULE', 'EVENT', 'WRAPUP']


def in_stage(event, stage):
    return STAGES[stage]['method'](event)


def get_stages(event):
    inactive_state = 'done'
    stages = copy.deepcopy(STAGES)

    for stage in STAGES:
        is_stage_active = inactive_state == 'done' and in_stage(event, stage)
        if is_stage_active:
            inactive_state = 'next'
        stages[stage]['state'] = 'active' if is_stage_active else inactive_state
    return stages
