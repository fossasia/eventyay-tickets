from django import template

register = template.Library()


def _review_score_number(context, score):
    if score is None:
        return "×"

    score = round(score, 1)
    if not context:
        return str(score)
    if isinstance(score, int) or (int(score) == score):
        score = int(score)
    return str(score)


@register.simple_tag(takes_context=True)
def review_score(context, submission, user_score=False):
    score = submission.current_score if not user_score else submission.user_score
    if score is None:
        return "-"
    return _review_score_number(context, score)
