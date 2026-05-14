from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if not isinstance(dictionary, dict):
        return ''
    return dictionary.get(key, '')
