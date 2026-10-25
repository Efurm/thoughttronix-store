import pytest

from .forms import ReviewForm

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("comment", "valid"),
    [
        ("x" * 9, False),
        (" " * 40, False),
        ("   " + "x" * 9 + "   ", False),
        ("x" * 10, True),
        ("x" * 2000, True),
        ("x" * 2001, False),
    ],
    ids=["9 chars", "spaces only", "9 chars padded", "10", "2000", "2001"],
)
def test_comment_must_be_10_to_2000_characters_after_trimming(comment, valid):
    form = ReviewForm(data={"rating": 4, "comment": comment})

    assert form.is_valid() is valid
    if not valid:
        assert "comment" in form.errors
