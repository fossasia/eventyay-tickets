import random
from abc import ABCMeta

from django.utils.translation import gettext_lazy as _

_phrase_book = {}


class PhrasesMetaClass(ABCMeta):
    def __new__(mcs, class_name, bases, namespace, app):
        new = super().__new__(mcs, class_name, bases, namespace)
        _phrase_book[app] = new()
        return new

    def __init__(cls, *args, app, **kwargs):
        super().__init__(*args, **kwargs)


class Phrases(metaclass=PhrasesMetaClass, app=""):
    def __getattribute__(self, attribute):
        result = super().__getattribute__(attribute)
        if isinstance(result, (list, tuple)):
            return random.choice(result)
        return result


class PhraseBook:
    def __getattribute__(self, attribute):
        return _phrase_book.get(attribute)


phrases = PhraseBook()


class BasePhrases(Phrases, app="base"):
    """This class contains base phrases that are guaranteed to remain the same
    (i.e., are not randomly chosen).

    They are still provided as a list to make it possible to combine
    them with new phrases in other classes.
    """

    send = [_("Send")]
    save = [_("Save")]
    cancel = [_("Cancel")]
    edit = [_("Edit")]

    saved = [_("Your changes have been saved.")]

    error_sending_mail = [
        _("There was an error sending the mail. Please try again later.")
    ]
    error_saving_changes = [
        _("Huh. We had trouble saving your input – Please see below for details. 🠯")
    ]
    error_permissions_action = [_("You do not have permission to perform this action.")]

    permission_denied = [
        _("Permission denied."),
        _("Sorry, you do not have the required permissions to access this page."),
        _("Access denied."),
    ]
    not_found = [
        _("Page not found."),
        _("This page does not exist."),
        _("Huh, I could have sworn there was something here."),
        "",
        _("This page is no more."),
        _("This page has ceased to be."),
        _("Huh."),
    ]

    enter_email = _("Email address")
    password_repeat = _("New password (again)")
    passwords_differ = _(
        "You entered two different passwords. Please input the same one twice!"
    )
    password_too_weak = [
        _("Your password is too weak or too common, please choose another one."),
        _("Sorry, this password is too weak or too common, please choose another one."),
        _(
            "Your password is the only thing protecting your account, so please choose a strong one."
        ),
    ]
    use_markdown = _("You can use {link_start}Markdown{link_end} here.").format(
        link_start=f'<a href="https://docs.pretalx.org/en/latest/user/markdown.html" target="_blank" rel="noopener">',
        link_end="</a>",
    )
    public_content = _("This content will be shown publicly.")
