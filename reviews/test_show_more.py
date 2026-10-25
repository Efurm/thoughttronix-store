"""Show more: a product's other reviews, 10 at a time, appended in place."""

import re
from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .models import Review

pytestmark = pytest.mark.django_db

MORE_BUTTON = 'id="review-more"'


@pytest.fixture
def many_reviews(product):
    """Build ``count`` reviews of the product by fresh customers, review 1
    the oldest; returns them newest first."""

    def build(count):
        now = timezone.now()
        reviews = []
        for n in range(1, count + 1):
            user = get_user_model().objects.create_user(
                username=f"reviewer{n}", email=f"reviewer{n}@example.com"
            )
            review = Review.objects.create(
                product=product, user=user, rating=4, comment=f"Review number {n}."
            )
            # Distinct stamps, a minute apart, so newest-first is unambiguous.
            when = now - timedelta(minutes=count - n)
            Review.objects.filter(pk=review.pk).update(created_at=when, updated_at=when)
            reviews.append(review)
        return reviews[::-1]

    return build


def more_url(product, number):
    return reverse("reviews:more", args=[product.pk, number])


def review_ids(html):
    return [int(pk) for pk in re.findall(r'<article id="review-(\d+)"', html)]


def ids(reviews):
    return [review.pk for review in reviews]


# --- The first batch on the product page ---------------------------------------


def test_the_page_shows_the_10_newest_and_a_button(client, product, many_reviews):
    reviews = many_reviews(25)

    html = client.get(product.get_absolute_url()).content.decode()

    assert review_ids(html) == ids(reviews[:10])
    assert MORE_BUTTON in html
    assert more_url(product, 2) in html


def test_exactly_10_reviews_show_no_button(client, product, many_reviews):
    many_reviews(10)

    html = client.get(product.get_absolute_url()).content.decode()

    assert len(review_ids(html)) == 10
    assert MORE_BUTTON not in html


# --- Later pages ---------------------------------------------------------------


def test_page_2_returns_the_next_10_and_a_button(client, product, many_reviews):
    reviews = many_reviews(25)

    response = client.get(more_url(product, 2))
    html = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert review_ids(html) == ids(reviews[10:20])
    assert more_url(product, 3) in html


def test_page_3_returns_the_last_5_and_no_button(client, product, many_reviews):
    reviews = many_reviews(25)

    html = client.get(more_url(product, 3)).content.decode()

    assert review_ids(html) == ids(reviews[20:])
    assert MORE_BUTTON not in html


def test_an_out_of_range_page_returns_no_reviews_and_no_button(
    client, product, many_reviews
):
    many_reviews(25)

    response = client.get(more_url(product, 4))
    html = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert review_ids(html) == []
    assert MORE_BUTTON not in html


def test_page_0_is_not_found(client, product):
    assert client.get(more_url(product, 0)).status_code == HTTPStatus.NOT_FOUND


def test_an_unknown_product_is_not_found(client):
    assert client.get(reverse("reviews:more", args=[999, 2])).status_code == (
        HTTPStatus.NOT_FOUND
    )


def test_show_more_is_public(client, product, many_reviews):
    many_reviews(11)

    response = client.get(more_url(product, 2))

    assert response.status_code == HTTPStatus.OK
    assert len(review_ids(response.content.decode())) == 1


def test_the_response_is_a_partial(client, product, many_reviews):
    many_reviews(11)

    html = client.get(more_url(product, 2)).content.decode()

    assert "<html" not in html


# --- The viewer's own review ----------------------------------------------------


def test_a_customers_own_review_never_appears_in_any_page(
    client, product, customer, many_reviews
):
    others = many_reviews(25)
    own = Review.objects.create(
        product=product, user=customer, rating=5, comment="My own thoughts."
    )
    client.force_login(customer)

    first = client.get(product.get_absolute_url()).content.decode()
    # The own card sits in the slot, never in the list.
    listed = review_ids(first.split('id="review-list"', 1)[1])
    for number in (2, 3, 4):
        listed += review_ids(client.get(more_url(product, number)).content.decode())

    assert own.pk not in listed
    assert listed == ids(others)
