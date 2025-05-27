from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter(name='is_authenticated')
def is_authenticated(user):
    return user.is_authenticated 