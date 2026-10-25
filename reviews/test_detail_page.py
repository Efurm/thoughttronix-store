"""The Reviews section of the product detail page (read-only)."""

from datetime import timedelta
from urllib.parse import quote

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Review

pytestmark = pytest.mark.django_db

BUYERS_ONLY = "Only customers who've bought the Seraphine Home Hub can review it"
SIGN_IN = "Sign in to leave a review"


@pytest.fixture
def make_customer(db):
    def build(username):
        return get_user_model().objects.create_user(
            username=username, email=f"{username}@example.com", password="pw"
        )

    return build


def review_of(product, user, rating=4, comment="Listens beautifully.", days_ago=0):
    review = Review.objects.create(
        product=product, user=user, rating=rating, comment=comment
    )
    if days_ago:
        # Backdate both stamps together, so the review doesn't read as edited.
        when = timezone.now() - timedelta(days=days_ago)
        Review.objects.filter(pk=review.pk).update(created_at=when, updated_at=when)
        review.refresh_from_db()
    return review


def page(client, product):
    return client.get(product.get_absolute_url())


# --- Summary and list -----------------------------------------------------------


def test_summary_shows_the_average_and_count(client, product, make_customer):
    review_of(product, make_customer("ada"), rating=5)
    review_of(product, make_customer("bo"), rating=4)

    html = page(client, product).content.decode()

    assert "4.5" in html
    assert "2 reviews" in html


def test_one_review_is_singular(client, product, customer):
    review_of(product, customer)

    assert "1 review</span>" in page(client, product).content.decode()


def test_no_reviews_shows_the_empty_state(client, product):
    html = page(client, product).content.decode()

    assert "No reviews yet" in html


def test_reviews_are_listed_newest_first(client, product, make_customer):
    review_of(product, make_customer("ada"), comment="The oldest thoughts.", days_ago=3)
    review_of(product, make_customer("bo"), comment="The newest thoughts.")
    review_of(product, make_customer("cy"), comment="The middle thoughts.", days_ago=1)

    html = page(client, product).content.decode()

    assert (
        html.index("The newest thoughts.")
        < html.index("The middle thoughts.")
        < html.index("The oldest thoughts.")
    )


def test_the_first_page_holds_ten_and_knows_more_exist(client, product, make_customer):
    for n in range(11):
        review_of(product, make_customer(f"buyer{n}"), days_ago=n + 1)

    context = page(client, product).context

    assert len(context["other_reviews"]) == 10
    assert context["more_reviews"]


def test_ten_reviews_means_no_more(client, product, make_customer):
    for n in range(10):
        review_of(product, make_customer(f"buyer{n}"))

    assert not page(client, product).context["more_reviews"]


def test_comments_are_escaped_with_line_breaks_kept(client, product, customer):
    review_of(product, customer, comment="<script>alert(1)</script>\nSecond line.")

    html = page(client, product).content.decode()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;<br>Second line." in html


def test_reviewer_and_date_are_shown(client, product, customer):
    customer.first_name, customer.last_name = "Casey", "Monroe"
    customer.save()
    review = review_of(product, customer)

    html = page(client, product).content.decode()

    assert "Casey Monroe" in html
    assert (
        f"{review.created_at:%b} {review.created_at.day}, {review.created_at.year}"
        in html
    )


def test_edit_marks_are_shown(client, product, customer, staff_user, make_customer):
    later = timezone.now() + timedelta(minutes=5)
    by_author = review_of(product, customer, comment="Author edited this.")
    by_staff = review_of(product, make_customer("bo"), comment="Staff edited this.")
    Review.objects.filter(pk=by_author.pk).update(updated_at=later, updated_by=customer)
    Review.objects.filter(pk=by_staff.pk).update(
        updated_at=later, updated_by=staff_user
    )

    html = page(client, product).content.decode()

    assert html.count("Edited by ThoughtTronix staff") == 1
    assert html.count(">Edited<") == 1


# --- The your-review slot ---------------------------------------------------------


def test_signed_out_visitors_are_invited_to_sign_in_and_come_back(client, product):
    html = page(client, product).content.decode()

    assert SIGN_IN in html
    assert f"?next={quote(product.get_absolute_url())}" in html


def test_a_buyer_sees_the_write_slot(client, product, customer, make_order):
    make_order(customer, product)
    client.force_login(customer)

    response = page(client, product)

    assert response.context["can_review"]
    assert response.context["own_review"] is None
    assert BUYERS_ONLY not in response.content.decode()
    assert SIGN_IN not in response.content.decode()


def test_a_non_buyer_is_told_only_buyers_can_review(client, product, customer):
    client.force_login(customer)

    assert BUYERS_ONLY in page(client, product).content.decode()


def test_staff_see_no_slot_message(client, product, staff_user, make_order):
    make_order(staff_user, product)
    client.force_login(staff_user)

    response = page(client, product)
    html = response.content.decode()

    assert not response.context["can_review"]
    assert BUYERS_ONLY not in html
    assert SIGN_IN not in html


def test_the_viewers_own_review_sits_in_the_slot_not_the_list(
    client, product, customer, make_order, make_customer
):
    make_order(customer, product)
    own = review_of(product, customer, comment="My very own thoughts.")
    other = review_of(product, make_customer("bo"), comment="Someone else's.")
    client.force_login(customer)

    response = page(client, product)
    html = response.content.decode()

    assert response.context["own_review"] == own
    assert response.context["other_reviews"] == [other]
    assert not response.context["can_review"]
    assert html.index("My very own thoughts.") < html.index('id="review-list"')
    assert html.count('id="review-' + str(own.pk) + '"') == 1


def test_others_see_that_review_in_the_list(client, product, customer):
    own = review_of(product, customer)

    assert page(client, product).context["other_reviews"] == [own]
