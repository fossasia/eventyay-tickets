from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def review_score(context, score):
    max_score = context['request'].event.settings.get('review_max_score')
    if score is None:
        return 'ø'

    if isinstance(score, int) or (isinstance(score, float) and score.is_integer()):
        score = int(score)
        name = context['request'].event.settings.get(f'review_score_name_{score}')
        if name:
            return f'{score}/{max_score} (»{name}«)'

    return f'{score}/{max_score}'
