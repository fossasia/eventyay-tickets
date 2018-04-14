from django.utils.translation import ugettext as _

from pretalx.common.phrases import Phrases


class OrgaPhrases(Phrases, app='orga'):

    logged_in = [
        _('Hi, nice to see you!'),
        _('Welcome!'),
        _('I hope you are having a good day :)'),
        _('Remember: organising events is lots of work, but it pays off.'),
        _('If you are waiting for feedback from your speakers, try sending a mail to a subset of them.'),
        _('Remember to provide your speakers with all information they need ahead of time.'),
        _('Even the busiest event organisers should make time to see at least one talk ;)'),
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
        _('I have heard a similar talk by this speaker, and I think ...'),
        _('In my opinion, this talk will appeal to ...'),
        _('While I think the talk is a great fit, it might be improved by ...'),
    ]
    another_review = [
        _('You\'re on a roll!'),
        _('"Just ONE more review, promise …"'),
        _('Review saved, thanks!'),
        _('One down, ... some more to go!'),
        _('Conferences build on good talk selection – which builds on reviewers like you!'),
        _('Remember to take a break between reviews, occasionally.'),
    ]
