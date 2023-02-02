from django.utils.translation import gettext as _

from pretalx.common.phrases import Phrases


class OrgaPhrases(Phrases, app="orga"):
    schedule_example_version = [
        "v1",
        "v2",
        "v4.0",
        "v0.1",
        "♥",
    ]
    example_review = [
        _("I think this session is well-suited to this conference, because ..."),
        _("I think this session might fit the conference better, if ..."),
        _("I think this session sounds like a perfect fit for Day 2, since ..."),
        _("I think this session might be improved by adding ..."),
        _("I have heard a similar session by this speaker, and I think ..."),
        _("In my opinion, this session will appeal to ..."),
        _("While I think the session is a great fit, it might be improved by ..."),
    ]
