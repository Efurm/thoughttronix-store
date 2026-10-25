"""The review form — one ``ModelForm`` for writing and editing a review.

Its rules sit at the field declarations, as on ``CheckoutForm``: the
rating is one of five whole stars, and the comment is trimmed, then
must be 10 to 2,000 characters. ``user``, ``product`` and ``updated_by``
are never fields; the view sets them from the request.
"""

from django import forms

from .models import Review

COMMENT_MIN = 10
COMMENT_MAX = 2000


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Rating",
        choices=[
            (stars, f"{stars} star{'s' if stars > 1 else ''}") for stars in range(1, 6)
        ],
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Choose a rating from 1 to 5 stars.",
            "invalid_choice": "Choose a rating from 1 to 5 stars.",
        },
    )
    # CharField strips leading and trailing whitespace before the length
    # checks, so padding can't pass a short comment off as a long one.
    comment = forms.CharField(
        label="Your review",
        min_length=COMMENT_MIN,
        max_length=COMMENT_MAX,
        widget=forms.Textarea(attrs={"class": "textarea w-full", "rows": 5}),
        error_messages={
            "required": "Write a few words about it.",
            "min_length": (
                f"Write at least {COMMENT_MIN} characters (you wrote %(show_value)d)."
            ),
            "max_length": (
                f"Keep it to {COMMENT_MAX:,} characters (you wrote %(show_value)d)."
            ),
        },
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
