from django.utils.translation import ugettext as _

from pretalx.common.phrases import Phrases


class OrgaPhrases(Phrases, app='orga'):

    logged_in = [
        _('Hi, nice to see you!'),
        _('Welcome!'),
        _('I hope you are having a good day :)'),
        _('Remember: organizing events is lots of work, but it pays off.'),
        _('If you are waiting for feedback from your speakers, try sending a mail to a subset of them.'),
        _('Remember to provide your speakers with all information they need ahead of time.'),
        _('Even the busiest event organizers should make time to see at least one talk ;)'),
    ]
    schedule_example_version = [
        'v1', 'v2', 'v4.0', 'v0.1', '♥',
    ]
    example_answer = [
        _('Pudding'), _('Panna cotta'), _('Chocolate chip cookies'),
    ]
    example_review = [
        _('I think this talk is well-suited to this conference, because ...'),
        _('I think this talk might fit the conference better, if ...'),
        _('I think this talk sounds like a perfect fit for Day 2, since ...'),
        _('I think this talk might be improved by adding ...'),
    ]
    another_review = [
        _('You\'re on a roll!'),
        _('"Just ONE more review, promise …"'),
        _('Review saved, thanks.'),
    ]
