"""The review form, shared by create and edit.

Validation is declarative, as on the checkout form: the comment field
strips leading and trailing whitespace before its length rules run, so
padding can't stretch a short comment past the minimum.
"""

from django import forms

from .models import Review

COMMENT_MIN = 10
COMMENT_MAX = 2000


class ReviewForm(forms.ModelForm):
    """A rating of 1–5 whole stars and a plain-text comment."""

    comment = forms.CharField(
        strip=True,
        min_length=COMMENT_MIN,
        max_length=COMMENT_MAX,
        widget=forms.Textarea(
            attrs={
                "class": "textarea w-full",
                "rows": 5,
                "placeholder": "How has it been, living with it?",
            }
        ),
        error_messages={
            "required": "Tell us what you thought.",
            "min_length": (
                f"Say a little more — at least {COMMENT_MIN} characters "
                "(you have %(show_value)d)."
            ),
            "max_length": (
                f"Keep it to {COMMENT_MAX:,} characters (you have %(show_value)d)."
            ),
        },
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        error_messages = {
            "rating": {
                "required": "Pick a rating from 1 to 5 stars.",
                "min_value": "Pick a rating from 1 to 5 stars.",
                "max_value": "Pick a rating from 1 to 5 stars.",
                "invalid": "Pick a rating from 1 to 5 stars.",
            }
        }
