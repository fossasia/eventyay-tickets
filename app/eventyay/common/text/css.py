import re

from cssutils import CSSParser
from cssutils.css import CSSMediaRule
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

acceptable_css_keywords = {
    "auto",
    "aqua",
    "black",
    "block",
    "blue",
    "bold",
    "both",
    "bottom",
    "brown",
    "center",
    "collapse",
    "contain",
    "cover",
    "dashed",
    "dotted",
    "fuchsia",
    "gray",
    "green",
    "!important",
    "italic",
    "left",
    "lime",
    "maroon",
    "medium",
    "none",
    "navy",
    "normal",
    "nowrap",
    "olive",
    "page",
    "pointer",
    "purple",
    "red",
    "right",
    "solid",
    "silver",
    "teal",
    "top",
    "transparent",
    "underline",
    "white",
    "yellow",
    "double",
}
valid_css_values = re.compile(
    r"^(#[0-9a-f]+|rgb\(\d+%?,\d*%?,?\d*%?\)?|\d{0,2}\.?\d{0,2}(cm|em|ex|in|mm|pc|pt|px|%|,|\))?)$"
)
acceptable_css_properties = {
    "azimuth",
    "background-color",
    "border-bottom-color",
    "border-collapse",
    "border-color",
    "border-left-color",
    "border-right-color",
    "border-top-color",
    "break-after",
    "clear",
    "color",
    "cursor",
    "direction",
    "display",
    "elevation",
    "float",
    "font",
    "font-family",
    "font-size",
    "font-style",
    "font-variant",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "max-width",
    "min-width",
    "object-fit",
    "overflow",
    "pause",
    "pause-after",
    "pause-before",
    "pitch",
    "pitch-range",
    "richness",
    "speak",
    "speak-header",
    "speak-numeral",
    "speak-punctuation",
    "speech-rate",
    "stress",
    "text-align",
    "text-decoration",
    "text-indent",
    "unicode-bidi",
    "vertical-align",
    "voice-family",
    "volume",
    "white-space",
    "width",
}


def validate_key(*, key, style):
    if key in acceptable_css_properties:
        return
    if key.split("-")[0] in ("background", "border", "margin", "padding"):
        for value in style[key].split(" "):
            if value not in acceptable_css_keywords and not valid_css_values.match(
                value
            ):
                raise ValidationError(
                    _("“{value}” is not allowed as attribute of “{key}”").format(
                        key=key, value=value
                    )
                )
    else:
        raise ValidationError(
            _("You are not allowed to include “{key}” keys in your CSS.").format(
                key=key
            )
        )


def validate_rules(rules):
    for rule in rules:
        if isinstance(rule, CSSMediaRule):
            validate_rules(rule.cssRules)
        else:
            style = rule.style
            for key in style.keys():
                validate_key(key=key, style=style)


def validate_css(css):
    try:
        parser = CSSParser(raiseExceptions=True, parseComments=False)
        stylesheet = parser.parseString(css)
    except Exception as exception:
        raise ValidationError(str(exception).split("\n")[0])
    validate_rules(stylesheet.cssRules)
    return css
