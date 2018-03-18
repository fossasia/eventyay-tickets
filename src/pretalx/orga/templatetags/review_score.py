from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _review_score_number(context, score):
    max_score = context['request'].event.settings.get('review_max_score')
    if score is None:
        return 'ø'

    if isinstance(score, int) or (isinstance(score, float) and score.is_integer()):
        score = int(score)
        name = context['request'].event.settings.get(f'review_score_name_{score}')
        if name:
            return f'{score}/{max_score} (»{name}«)'
    else:
        score = round(score, 1)

    return f'{score}/{max_score}'


def _review_score_override(positive_overrides, negative_overrides):
    result = ''
    if positive_overrides:
        result += f'<i class="fa fa-arrow-circle-up override text-success"></i>'
        if positive_overrides > 1 or negative_overrides:
            result += f' {positive_overrides}'
    if negative_overrides:
        result += f'<i class="fa fa-arrow-circle-down override text-danger"></i>'
        if negative_overrides > 1 or positive_overrides:
            result += f' {negative_overrides}'
    return result


@register.simple_tag(takes_context=True)
def review_score(context, submission):
    score = submission.average_score
    positive_overrides = submission.reviews.filter(override_vote=True).count()
    negative_overrides = submission.reviews.filter(override_vote=False).count()

    if positive_overrides or negative_overrides:
        return mark_safe(_review_score_override(positive_overrides, negative_overrides))

    return _review_score_number(context, score)
