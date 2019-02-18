from django.utils.translation import ugettext_lazy as _


def get_help_text(text, min_length, max_length, count_in='chars'):
    if not min_length and not max_length:
        return text
    if text:
        text = str(text) + ' '
    else:
        text = ''
    texts = {
        'minmaxwords': _('Please write between {min_length} and {max_length} words.'),
        'minmaxchars': _('Please write between {min_length} and {max_length} characters.'),
        'minwords': _('Please write at least {min_length} words.'),
        'minchars': _('Please write at least {min_length} characters.'),
        'maxwords': _('Please write at most {max_length} words.'),
        'maxchars': _('Please write at most {max_length} characters.'),
    }
    length = ('min' if min_length else '') + ('max' if max_length else '')
    message = texts[length + count_in].format(min_length=min_length, max_length=max_length)
    return (text + str(message)).strip()
