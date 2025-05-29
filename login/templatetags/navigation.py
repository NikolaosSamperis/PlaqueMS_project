from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def active(context, *url_names):
    """
    Usage:  class="{% active 'home' %}"
    Returns the word 'active' if the current URL-name
    matches any of the names given.
    """
    current = context["request"].resolver_match.url_name
    return "active" if current in url_names else ""