from django.utils.translation import ugettext as _

from pretalx.common.messages import Messages


class AgendaMessages(Messages, app='agenda'):
    feedback_success = [
        _('Thank you for your feedback!'),
        _('Thanks, we (and our speakers) appreciate your feedback!'),
    ]
