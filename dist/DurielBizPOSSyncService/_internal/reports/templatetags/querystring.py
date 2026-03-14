from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def update_query(context, key, value):
    request = context["request"]
    query = request.GET.copy()
    if value in (None, ""):
        query.pop(key, None)
    else:
        query[key] = value

    encoded = query.urlencode()
    return f"?{encoded}" if encoded else "?"
