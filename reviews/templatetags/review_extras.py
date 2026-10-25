from django import template

register = template.Library()


@register.filter
def can_change(review, user):
    """Ask the model's own rule from a template: ``review|can_change:user``."""
    return review.can_change(user)
