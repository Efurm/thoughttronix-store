from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .models import Review

pytestmark = pytest.mark.django_db


def comment(number):
    return f"Thought #{number:02d}, recorded."


@pytest.fixture
def many_reviews(product):
    """25 reviews by different customers; #01 is the newest, #25 the oldest."""
    now = timezone.now()
    for number in range(1, 26):
        review = Review.objects.create(
            user=get_user_model().objects.create_user(username=f"reviewer{number}"),
            product=product,
            rating=4,
            comment=comment(number),
        )
        Review.objects.filter(pk=review.pk).update(
            created_at=now - timedelta(minutes=number)
        )


def more_url(product, page):
    return reverse("reviews:more", args=[product.pk, page])


@pytest.mark.parametrize(
    ("page", "first", "last", "next_page"),
    [(2, 11, 20, 3), (3, 21, 25, None), (4, None, None, None)],
    ids=["page 2", "page 3 (last)", "page 4 (past the end)"],
)
def test_show_more_returns_the_next_ten_newest_first(
    client, product, many_reviews, page, first, last, next_page
):
    content = client.get(more_url(product, page)).content.decode()

    shown = [n for n in range(1, 26) if comment(n) in content]
    expected = list(range(first, last + 1)) if first else []
    assert shown == expected
    positions = [content.index(comment(n)) for n in shown]
    assert positions == sorted(positions)
    for later in range(page + 1, 6):
        has_button = f'hx-get="{more_url(product, later)}"' in content
        assert has_button is (later == next_page)


def test_own_review_never_appears_and_shifts_no_page(
    client, customer, product, many_reviews
):
    """The customer's review sits between #05 and #06 — inside page 1 if it
    were listed, so counting it would push every later page back one."""
    own = Review.objects.create(
        user=customer, product=product, rating=5, comment="My own thought."
    )
    Review.objects.filter(pk=own.pk).update(
        created_at=timezone.now() - timedelta(minutes=5, seconds=30)
    )
    client.force_login(customer)

    page_2 = client.get(more_url(product, 2)).content.decode()
    page_3 = client.get(more_url(product, 3)).content.decode()

    assert [n for n in range(1, 26) if comment(n) in page_2] == list(range(11, 21))
    assert [n for n in range(1, 26) if comment(n) in page_3] == list(range(21, 26))
    assert "My own thought." not in page_2 + page_3
    assert f'hx-get="{more_url(product, 4)}"' not in page_3


def test_show_more_is_public(client, product, many_reviews):
    response = client.get(more_url(product, 2))

    assert response.status_code == HTTPStatus.OK


def test_page_zero_is_not_found(client, product):
    assert client.get(more_url(product, 0)).status_code == HTTPStatus.NOT_FOUND


def test_a_missing_product_is_not_found(client, db):
    response = client.get(reverse("reviews:more", args=[999, 2]))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_show_more_returns_a_partial(client, product, many_reviews):
    content = client.get(more_url(product, 2)).content.decode()

    assert "<html" not in content
    assert 'id="review-list"' not in content


def test_product_page_shows_ten_and_a_button_for_page_two(
    client, product, many_reviews
):
    content = client.get(product.get_absolute_url()).content.decode()

    assert [n for n in range(1, 26) if comment(n) in content] == list(range(1, 11))
    assert f'hx-get="{more_url(product, 2)}"' in content
    assert "Show more reviews" in content


def test_exactly_ten_reviews_show_no_button(client, product):
    for number in range(1, 11):
        Review.objects.create(
            user=get_user_model().objects.create_user(username=f"r{number}"),
            product=product,
            rating=3,
            comment=comment(number),
        )

    content = client.get(product.get_absolute_url()).content.decode()

    assert "Show more reviews" not in content


def test_product_page_leaves_out_own_review_from_the_first_batch(
    client, customer, product, many_reviews
):
    Review.objects.create(
        user=customer, product=product, rating=5, comment="My own thought."
    )
    client.force_login(customer)

    content = client.get(product.get_absolute_url()).content.decode()
    list_part = content[content.index('id="review-list"') :]

    assert [n for n in range(1, 26) if comment(n) in list_part] == list(range(1, 11))
    assert "My own thought." not in list_part
    assert f'hx-get="{more_url(product, 2)}"' in list_part


def test_staff_get_edit_and_delete_on_loaded_reviews(
    client, staff_user, product, many_reviews
):
    client.force_login(staff_user)

    content = client.get(more_url(product, 2)).content.decode()

    assert content.count(">Edit</button>") == 10
    assert content.count(">Delete</button>") == 10
