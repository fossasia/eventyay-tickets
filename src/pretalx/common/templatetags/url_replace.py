from django import template

register = template.Library()


@register.simple_tag
def url_replace(request, *pairs):
    dict_ = request.GET.copy()
    key = None
    for pair in pairs:
        if key is None:
            key = pair
        else:
            if pair == "":
                if key in dict_:
                    del dict_[key]
            else:
                dict_[key] = str(pair)
            key = None
    return dict_.urlencode(safe="[]")
