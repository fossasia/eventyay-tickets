import re

from cssutils import CSSParser
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

acceptable_css_keywords = set([
    'auto', 'aqua', 'black', 'block', 'blue', 'bold', 'both', 'bottom',
    'brown', 'center', 'collapse', 'dashed', 'dotted', 'fuchsia', 'gray',
    'green', '!important', 'italic', 'left', 'lime', 'maroon', 'medium',
    'none', 'navy', 'normal', 'nowrap', 'olive', 'pointer', 'purple', 'red',
    'right', 'solid', 'silver', 'teal', 'top', 'transparent', 'underline',
    'white', 'yellow', 'double',
])
valid_css_values = re.compile('^(#[0-9a-f]+|rgb\(\d+%?,\d*%?,?\d*%?\)?|\d{0,2}\.?\d{0,2}(cm|em|ex|in|mm|pc|pt|px|%|,|\))?)$')
acceptable_css_properties = set([
    'azimuth', 'background-color', 'border-bottom-color', 'border-collapse',
    'border-color', 'border-left-color', 'border-right-color',
    'border-top-color', 'clear', 'color', 'cursor', 'direction', 'display',
    'elevation', 'float', 'font', 'font-family', 'font-size', 'font-style',
    'font-variant', 'font-weight', 'height', 'letter-spacing', 'line-height',
    'max-width', 'min-width', 'overflow', 'pause', 'pause-after',
    'pause-before', 'pitch', 'pitch-range', 'richness', 'speak',
    'speak-header', 'speak-numeral', 'speak-punctuation', 'speech-rate',
    'stress', 'text-align', 'text-decoration', 'text-indent', 'unicode-bidi',
    'vertical-align', 'voice-family', 'volume', 'white-space', 'width',
])


def validate_key(*, key, style):
    if key in acceptable_css_properties:
        return
    elif key.split('-')[0] in ['background', 'border', 'margin', 'padding']:
        for value in style[key].split(' '):
            if value not in acceptable_css_keywords and not valid_css_values.match(value):
                raise ValidationError(_('"{value}" is not allowed as attribute of "{key}"').format(key=key, value=value))
    else:
        raise ValidationError(_('You are not allowed to include "{key}" keys in your CSS.').format(key=key))


def validate_css(css):
    try:
        parser = CSSParser(raiseExceptions=True)
        stylesheet = parser.parseString(css)
    except Exception as e:
        raise ValidationError(str(e).split('\n')[0])

    if not stylesheet.valid:
        raise ValidationError(_('This stylesheet is not valid CSS.'))

    for rule in stylesheet.cssRules:
        style = rule.style
        for key in style.keys():
            validate_key(key=key, style=style)
    return css
