from django.utils.translation import ugettext as _

from pretalx.common.phrases import Phrases


class OrgaPhrases(Phrases, app='orga'):

    schedule_example_version = [
        'v1', 'v2', 'v4.0', 'v0.1', '♥',
    ]
    example_answer = [
        _('Built bridges'), _('Built aqueducts'), _('Built roads'),
        _('Introduced medicine'), _('Expanded education'),
    ]
    example_review = [
        _('I think this talk is well-suited to this conference, because ...'),
        _('I think this talk might fit the conference better, if ...'),
        _('I think this talk sounds like a perfect fit for Day 2, since ...'),
        _('I think this talk might be improved by adding ...'),
    ]
