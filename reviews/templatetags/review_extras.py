from django import template

register = template.Library()


@register.filter
def can_change(review, user):
    """Whether ``user`` may edit or delete ``review`` — the model's own rule,
    so a card shows its controls exactly when the server would allow them."""
    return review.can_change(user)
