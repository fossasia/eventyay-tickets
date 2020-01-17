import math

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

register = template.Library()


def _review_score_number(context, score):
    if score is None:
        return "×"

    score = round(score, 1)
    if not context:
        return str(score)
    max_score = context["request"].event.settings.get("review_max_score")
    if isinstance(score, int) or (isinstance(score, float) and score.is_integer()):
        score = int(score)
        tooltip = (
            context["request"].event.settings.get(f"review_score_name_{score}") or ""
        )
        if tooltip:
            tooltip = f"'{tooltip}'"
    else:
        lower_bound = math.floor(score)
        lower = context["request"].event.settings.get(
            f"review_score_name_{lower_bound}"
        )
        upper = context["request"].event.settings.get(
            f"review_score_name_{lower_bound + 1}"
        )
        tooltip = _("Between '{lower}' and '{upper}'.").format(lower=lower, upper=upper)
    result = f"{score}/{max_score}"
    if not tooltip:
        return result
    return format_html(
        '<span data-toggle="tooltip" title="{}">{}</span>', tooltip, result
    )


def _review_score_override(positive_overrides, negative_overrides):
    result = ""
    if positive_overrides:
        result += f'<i class="fa fa-arrow-circle-up override text-success"></i>'
        if positive_overrides > 1 or negative_overrides:
            result += f" {positive_overrides}"
    if negative_overrides:
        result += f'<i class="fa fa-arrow-circle-down override text-danger"></i>'
        if negative_overrides > 1 or positive_overrides:
            result += f" {negative_overrides}"
    return result


@register.simple_tag(takes_context=True)
def review_score(context, submission, user_score=False):
    score = submission.current_score if not user_score else submission.user_score
    if score is None:
        return "-"
    if hasattr(submission, "has_override") and not submission.has_override:
        return _review_score_number(context, score)
    positive_overrides = submission.reviews.filter(override_vote=True).count()
    negative_overrides = submission.reviews.filter(override_vote=False).count()
    if positive_overrides or negative_overrides:
        return mark_safe(_review_score_override(positive_overrides, negative_overrides))
    return _review_score_number(context, score)
