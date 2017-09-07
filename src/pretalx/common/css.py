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
    'white', 'yellow',
])
valid_css_values = re.compile('^(#[0-9a-f]+|rgb\(\d+%?,\d*%?,?\d*%?\)?|\d{0,2}\.?\d{0,2}(cm|em|ex|in|mm|pc|pt|px|%|,|\))?)$')
acceptable_css_properties = set([
    'azimuth', 'background-color', 'border-bottom-color', 'border-collapse',
    'border-color', 'border-left-color', 'border-right-color', 'border-top-color',
    'clear', 'color', 'cursor', 'direction', 'display', 'elevation', 'float', 'font',
    'font-family', 'font-size', 'font-style', 'font-variant', 'font-weight', 'height',
    'letter-spacing', 'line-height', 'overflow', 'pause', 'pause-after', 'pause-before',
    'pitch', 'pitch-range', 'richness', 'speak', 'speak-header', 'speak-numeral',
    'speak-punctuation', 'speech-rate', 'stress', 'text-align', 'text-decoration',
    'text-indent', 'unicode-bidi', 'vertical-align', 'voice-family', 'volume',
    'white-space', 'width',
])
acceptable_svg_properties = set([
    'fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-linecap',
    'stroke-linejoin', 'stroke-opacity',
])


def get_key(style, key):

    while key.find('-') != -1:
        index = key.find('-')
        key = key[:index] + key[index + 1:].capitalize()

    return getattr(style, key)


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
            values = get_key(style, key)
            if key in acceptable_css_properties:
                continue
            if not values:
                raise ValidationError(_('"{key}" attribute could not be parsed.').format(key=key))
            elif key.split('-')[0].lower() in ['background', 'border', 'margin', 'padding']:
                for value in values.split(' '):
                    if value not in acceptable_css_keywords and not valid_css_values.match(value):
                        raise ValidationError(_('"{value}" is not allowed as attribute of "{key}"').format(key=key, value=value))
            elif key.lower() not in acceptable_svg_properties:
                raise ValidationError(_('You are not allowed to include "{key}" keys in your CSS.').format(key=key))
    return css
