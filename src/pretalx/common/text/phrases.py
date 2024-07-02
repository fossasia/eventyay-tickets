import random
from abc import ABCMeta

from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

_phrase_book = {}


class PhrasesMetaClass(ABCMeta):  # noqa
    def __new__(cls, class_name, bases, namespace, app):
        new = super().__new__(cls, class_name, bases, namespace)
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
    """
    This class contains base phrases that are guaranteed to remain the same.
    """

    send = _("Send")
    save = _("Save")
    cancel = _("Cancel")
    edit = _("Edit")
    all_choices = _("all")
    back_button = _("Back")
    delete_button = _("Delete")

    delete_confirm_heading = _("Confirm deletion")
    delete_warning = _(
        "Please make sure that this is the item you want to delete. This action cannot be undone!"
    )

    saved = _("Your changes have been saved.")
    back_try_again = _("Please go back and try again.")
    bad_request = _("Bad request.")
    error_sending_mail = _(
        "There was an error sending the mail. Please try again later."
    )
    error_saving_changes = _(
        "We had trouble saving your input – Please see below for details."
    )
    error_permissions_action = _("You do not have permission to perform this action.")

    permission_denied = _("Permission denied.")
    permission_denied_long = (
        _("Sorry, you do not have the required permissions to access this page."),
    )
    not_found = _("Page not found.")
    not_found_long = [
        _("This page does not exist."),
        _("Huh, I could have sworn there was something here."),
        "",
        _("This page is no more."),
        _("This page has ceased to be."),
        _("Huh."),
    ]

    enter_email = _("Email address")
    new_password = _("New password")
    password_repeat = _("New password (again)")
    passwords_differ = _(
        "You entered two different passwords. Please enter the same one twice!"
    )
    password_reset_heading = pgettext_lazy("noun / heading", "Reset password")
    password_reset_question = _("Forgot your password?")
    password_reset_action = _("Let me set a new one!")
    password_reset_nearly_done = _(
        "Now you just need to choose your new password and you are ready to go."
    )
    password_reset_success = _("The password was reset.")

    use_markdown = _("You can use {link_start}Markdown{link_end} here.").format(
        link_start='<a href="https://en.wikipedia.org/wiki/Markdown" target="_blank" rel="noopener">',
        link_end="</a>",
    )
    public_content = _("This content will be shown publicly.")
    quotation_open = pgettext_lazy("opening quotation mark", "“")
    quotation_close = pgettext_lazy("closing quotation mark", "”")
    language = _("Language")
    general = _("General")
    email_subject = pgettext_lazy("email subject", "Subject")
    text_body = _("Text")
