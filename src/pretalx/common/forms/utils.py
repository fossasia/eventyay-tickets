from django.utils.translation import ugettext_lazy as _


def get_help_text(text, min_length, max_length):
    if not min_length and not max_length:
        return text
    text = str(text) + ' '
    if min_length and max_length:
        warning = _('Please write between {min} and {max} characters.').format(min=min_length, max=max_length)
    elif min_length:
        warning = _('Please write at least {min} characters.').format(min=min_length)
    else:
        warning = _('Please write no more than {max} characters.').format(max=max_length)
    return (text + warning).strip()
