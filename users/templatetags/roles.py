from django import template

register = template.Library()

@register.filter
def has_group(user, name):
    return user.is_authenticated and user.groups.filter(name=name).exists()
